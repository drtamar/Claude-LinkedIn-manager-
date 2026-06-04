import json
from datetime import datetime, timedelta, date
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models.ai_learning import PromptVersion, LearningCycle, AlgorithmInsight
from app.models.content import Post, PostMetrics
from app.ai.modules.learning_ai import analyze_performance, refine_prompt
from app.ai import prompt_registry


PERFORMANCE_THRESHOLD = 0.15  # 15% deviation triggers refinement
MIN_SAMPLE_SIZE = 5


def get_active_prompt_versions(db: Session) -> list[PromptVersion]:
    return db.query(PromptVersion).filter(PromptVersion.is_active == True).all()


def get_prompt_history(db: Session, module: str) -> list[PromptVersion]:
    return db.query(PromptVersion).filter(
        PromptVersion.module == module
    ).order_by(desc(PromptVersion.version)).all()


def rollback_prompt(db: Session, module: str, version_id: int) -> PromptVersion:
    # Deactivate current
    db.query(PromptVersion).filter(
        PromptVersion.module == module,
        PromptVersion.is_active == True,
    ).update({"is_active": False, "retired_at": datetime.utcnow()})

    # Activate target
    target = db.query(PromptVersion).filter(PromptVersion.id == version_id).first()
    if not target:
        raise ValueError(f"Version {version_id} not found")
    target.is_active = True
    target.retired_at = None
    db.commit()
    prompt_registry.invalidate_cache(module)
    return target


async def run_learning_cycle(db: Session, user_id: int) -> LearningCycle:
    cycle = LearningCycle(user_id=user_id, status="running")
    db.add(cycle)
    db.commit()
    db.refresh(cycle)

    try:
        cutoff = date.today() - timedelta(days=30)
        posts_with_metrics = (
            db.query(Post, PostMetrics)
            .join(PostMetrics)
            .filter(Post.user_id == user_id, Post.status == "published")
            .filter(Post.published_at >= datetime.combine(cutoff, datetime.min.time()))
            .all()
        )

        if not posts_with_metrics:
            cycle.status = "completed"
            cycle.full_report = "Not enough data yet. Publish and track more posts."
            cycle.insights = json.dumps({"message": "insufficient_data"})
            db.commit()
            return cycle

        posts_data = [
            {
                "id": p.id,
                "content": p.content[:300],
                "post_type": p.post_type,
                "hook": p.hook,
                "published_at": p.published_at.isoformat() if p.published_at else None,
                "prompt_version_id": p.generation_prompt_id,
                "impressions": m.impressions,
                "reactions": m.reactions,
                "comments": m.comments,
                "engagement_rate": m.engagement_rate,
            }
            for p, m in posts_with_metrics
        ]

        from app.models.profile import UserProfile
        from app.services.profile_service import user_profile_to_dict
        user_profile_obj = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        user_profile = user_profile_to_dict(user_profile_obj)

        prompt_versions = get_active_prompt_versions(db)
        pv_data = [{"module": pv.module, "version": pv.version, "id": pv.id} for pv in prompt_versions]

        analysis = await analyze_performance(user_profile, posts_data, pv_data)

        improvements_made = 0
        for suggestion in analysis.get("prompt_improvement_suggestions", []):
            if suggestion.get("priority") != "high":
                continue

            module = suggestion["module"]
            current_pv = db.query(PromptVersion).filter(
                PromptVersion.module == module,
                PromptVersion.is_active == True,
            ).first()
            if not current_pv:
                continue

            module_posts = [p for p in posts_data if p.get("prompt_version_id") == current_pv.id]
            if len(module_posts) < MIN_SAMPLE_SIZE:
                continue

            avg_engagement = sum(p["engagement_rate"] for p in module_posts) / len(module_posts)
            overall_avg = sum(p["engagement_rate"] for p in posts_data) / len(posts_data)

            if abs(avg_engagement - overall_avg) / max(overall_avg, 0.001) < PERFORMANCE_THRESHOLD:
                continue

            high_performers = sorted(module_posts, key=lambda x: x["engagement_rate"], reverse=True)[:3]
            refinement = await refine_prompt(
                module=module,
                current_prompt=current_pv.prompt_template,
                current_system=current_pv.system_message or "",
                performance_findings=analysis,
                high_performing_examples=[p["content"] for p in high_performers],
            )

            if "error" not in refinement and refinement.get("new_prompt_template"):
                current_pv.is_active = False
                current_pv.retired_at = datetime.utcnow()

                new_pv = PromptVersion(
                    module=module,
                    version=current_pv.version + 1,
                    prompt_template=refinement["new_prompt_template"],
                    system_message=refinement.get("new_system_message", current_pv.system_message),
                    model=current_pv.model,
                    is_active=True,
                    parent_version_id=current_pv.id,
                    change_reason=refinement.get("change_summary", ""),
                )
                db.add(new_pv)
                prompt_registry.invalidate_cache(module)
                improvements_made += 1

        # Save algorithm insights
        for finding in analysis.get("high_performing_patterns", []):
            insight = AlgorithmInsight(
                user_id=user_id,
                insight_type="engagement",
                insight_data=json.dumps(finding),
                confidence_score=0.8,
                based_on_posts=len(posts_data),
            )
            db.add(insight)

        cycle.status = "completed"
        cycle.improvements_made = improvements_made
        cycle.modules_analyzed = json.dumps([s["module"] for s in analysis.get("prompt_improvement_suggestions", [])])
        cycle.insights = json.dumps(analysis)
        cycle.full_report = json.dumps(analysis, indent=2)
        db.commit()

    except Exception as e:
        cycle.status = "failed"
        cycle.full_report = str(e)
        db.commit()
        raise

    return cycle

import json
from datetime import date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.models.analytics import SSIScore, NetworkStats
from app.models.content import Post, PostMetrics
from app.models.ai_learning import AlgorithmInsight


def get_dashboard_stats(db: Session, user_id: int) -> dict:
    # Posts this month
    today = date.today()
    month_start = today.replace(day=1)
    posts_this_month = db.query(Post).filter(
        Post.user_id == user_id,
        Post.status == "published",
        func.date(Post.published_at) >= month_start,
    ).count()

    # Latest SSI
    latest_ssi = db.query(SSIScore).filter(
        SSIScore.user_id == user_id
    ).order_by(desc(SSIScore.score_date)).first()

    # Avg engagement rate (last 10 posts)
    recent_metrics = (
        db.query(PostMetrics)
        .join(Post)
        .filter(Post.user_id == user_id)
        .order_by(desc(PostMetrics.scraped_at))
        .limit(10)
        .all()
    )
    avg_engagement = 0.0
    if recent_metrics:
        avg_engagement = sum(m.engagement_rate for m in recent_metrics) / len(recent_metrics)

    # Recent connections
    from app.models.network import ConnectionRequest
    connections_this_month = db.query(ConnectionRequest).filter(
        ConnectionRequest.user_id == user_id,
        ConnectionRequest.status == "accepted",
        func.date(ConnectionRequest.accepted_at) >= month_start,
    ).count()

    return {
        "ssi_score": latest_ssi.total_score if latest_ssi else 0,
        "posts_this_month": posts_this_month,
        "new_connections": connections_this_month,
        "avg_engagement_rate": round(avg_engagement * 100, 2),
    }


def get_post_metrics(db: Session, user_id: int, days: int = 30) -> list[dict]:
    cutoff = date.today() - timedelta(days=days)
    rows = (
        db.query(Post, PostMetrics)
        .join(PostMetrics)
        .filter(Post.user_id == user_id, func.date(Post.published_at) >= cutoff)
        .order_by(desc(Post.published_at))
        .all()
    )
    results = []
    for post, metrics in rows:
        results.append({
            "post_id": post.id,
            "title": post.title or post.content[:50],
            "post_type": post.post_type,
            "published_at": post.published_at.isoformat() if post.published_at else None,
            "impressions": metrics.impressions,
            "reactions": metrics.reactions,
            "comments": metrics.comments,
            "shares": metrics.shares,
            "engagement_rate": metrics.engagement_rate,
        })
    return results


def get_ssi_history(db: Session, user_id: int, weeks: int = 12) -> list[dict]:
    cutoff = date.today() - timedelta(weeks=weeks)
    scores = db.query(SSIScore).filter(
        SSIScore.user_id == user_id,
        SSIScore.score_date >= cutoff,
    ).order_by(SSIScore.score_date).all()
    return [
        {
            "date": s.score_date.isoformat(),
            "total": s.total_score,
            "brand": s.establish_brand,
            "people": s.find_right_people,
            "insights": s.engage_insights,
            "relationships": s.build_relationships,
        }
        for s in scores
    ]


def get_engagement_heatmap(db: Session, user_id: int) -> list[dict]:
    from sqlalchemy import extract
    rows = (
        db.query(
            extract("dow", Post.published_at).label("dow"),
            extract("hour", Post.published_at).label("hour"),
            func.avg(PostMetrics.engagement_rate).label("avg_engagement"),
            func.count(Post.id).label("count"),
        )
        .join(PostMetrics)
        .filter(Post.user_id == user_id, Post.status == "published")
        .group_by("dow", "hour")
        .all()
    )
    return [
        {
            "day": int(r.dow),
            "hour": int(r.hour),
            "avg_engagement": float(r.avg_engagement),
            "count": int(r.count),
        }
        for r in rows
    ]


def get_active_insights(db: Session, user_id: int) -> list[dict]:
    insights = db.query(AlgorithmInsight).filter(
        AlgorithmInsight.user_id == user_id,
        AlgorithmInsight.is_active == True,
    ).order_by(desc(AlgorithmInsight.generated_at)).limit(10).all()
    return [
        {
            "type": i.insight_type,
            "data": json.loads(i.insight_data) if i.insight_data else {},
            "confidence": i.confidence_score,
        }
        for i in insights
    ]

import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.services import profile_service as svc
from app.ai.modules.profile_ai import stream_about, generate_headline, score_profile, categorize_skills

router = APIRouter(prefix="/api/profile", tags=["profile"])


def profile_to_dict(p) -> dict:
    if not p:
        return {}
    return {
        "id": p.id,
        "version": p.version,
        "headline": p.headline,
        "headline_variants": json.loads(p.headline_variants or "[]"),
        "about_section": p.about_section,
        "experience": json.loads(p.experience_json or "[]"),
        "skills": json.loads(p.skills_json or "[]"),
        "skills_categorized": json.loads(p.skills_categorized_json or "{}") if hasattr(p, "skills_categorized_json") else {},
        "featured": json.loads(p.featured_json or "[]"),
        "profile_score": p.profile_score,
        "score_breakdown": json.loads(p.score_breakdown or "{}"),
    }


@router.get("/")
def get_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    p = svc.get_linkedin_profile(db, current_user.id)
    return profile_to_dict(p)


@router.post("/generate")
async def generate_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user_profile = svc.get_user_profile(db, current_user.id)
    if not user_profile:
        raise HTTPException(status_code=400, detail="Complete onboarding questionnaire first")
    profile = await svc.generate_full_profile(db, current_user)
    return profile_to_dict(profile)


@router.get("/stream/about")
async def stream_about_section(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user_profile_obj = svc.get_user_profile(db, current_user.id)
    if not user_profile_obj:
        raise HTTPException(status_code=400, detail="Complete questionnaire first")
    profile_dict = svc.user_profile_to_dict(user_profile_obj)

    li_profile = svc.get_linkedin_profile(db, current_user.id)
    headline = li_profile.headline if li_profile else ""
    has_profile = li_profile is not None
    user_id = current_user.id

    async def generate():
        from app.database import SessionLocal
        full_text = ""
        async for token in stream_about(profile_dict, headline):
            full_text += token
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
        if has_profile and full_text:
            db_write = SessionLocal()
            try:
                svc.update_profile_section(db_write, user_id, "about_section", full_text)
            finally:
                db_write.close()
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.put("/{section}")
def update_section(
    section: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    allowed = ["headline", "about_section", "experience_json", "skills_json", "featured_json"]
    if section not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid section: {section}")
    content = payload.get("content", "")
    p = svc.update_profile_section(db, current_user.id, section, content)
    return {"updated": section, "profile_id": p.id}


@router.post("/variants/{section}")
async def generate_variants(
    section: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if section != "headline":
        raise HTTPException(status_code=400, detail="Variants only available for headline currently")
    user_profile_obj = svc.get_user_profile(db, current_user.id)
    profile_dict = svc.user_profile_to_dict(user_profile_obj)
    result = await generate_headline(profile_dict)
    return result


@router.post("/categorize-skills")
async def categorize_profile_skills(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Group the user's skills into professional categories using AI."""
    p = svc.get_linkedin_profile(db, current_user.id)
    if not p:
        raise HTTPException(status_code=404, detail="Generate profile first")

    skills = json.loads(p.skills_json or "[]")
    if not skills:
        raise HTTPException(status_code=400, detail="No skills to categorize")

    user_profile_obj = svc.get_user_profile(db, current_user.id)
    user_profile_dict = svc.user_profile_to_dict(user_profile_obj) if user_profile_obj else None

    categorized = await categorize_skills(skills, user_profile_dict)

    p.skills_categorized_json = json.dumps(categorized)
    db.commit()

    return {"categories": categorized, "total_skills": len(skills)}


@router.get("/stream/cv")
async def stream_cv_export(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream a complete AI-generated CV from the user's LinkedIn profile data."""
    user_profile_obj = svc.get_user_profile(db, current_user.id)
    if not user_profile_obj:
        raise HTTPException(status_code=400, detail="Complete questionnaire first")

    profile_dict = svc.user_profile_to_dict(user_profile_obj)
    li_profile = svc.get_linkedin_profile(db, current_user.id)
    li_dict = profile_to_dict(li_profile)

    async def generate():
        from app.ai.modules.cv_ai import stream_cv
        async for token in stream_cv(profile_dict, li_dict):
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/export/cv")
async def export_cv_html(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate and download a print-ready HTML CV file."""
    from app.ai.modules.cv_ai import stream_cv, markdown_to_print_html

    user_profile_obj = svc.get_user_profile(db, current_user.id)
    if not user_profile_obj:
        raise HTTPException(status_code=400, detail="Complete questionnaire first")

    profile_dict = svc.user_profile_to_dict(user_profile_obj)
    li_profile = svc.get_linkedin_profile(db, current_user.id)
    li_dict = profile_to_dict(li_profile)

    cv_markdown = ""
    async for token in stream_cv(profile_dict, li_dict):
        cv_markdown += token

    display_name = current_user.display_name or "CV"
    html = markdown_to_print_html(cv_markdown, display_name)

    safe_name = "".join(c if c.isalnum() or c in "-_ " else "" for c in display_name).strip().replace(" ", "_")
    filename = f"{safe_name}_CV.html" if safe_name else "CV.html"

    return Response(
        content=html,
        media_type="text/html",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/score")
async def get_score(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    p = svc.get_linkedin_profile(db, current_user.id)
    if not p:
        raise HTTPException(status_code=404, detail="Generate profile first")
    skills = json.loads(p.skills_json or "[]")
    experience = json.loads(p.experience_json or "[]")
    score_data = await score_profile(
        headline=p.headline or "",
        about=p.about_section or "",
        skills=skills,
        experience=experience,
    )
    p.profile_score = score_data.get("total_score", 0)
    p.score_breakdown = json.dumps(score_data.get("breakdown", {}))
    db.commit()
    return score_data

import json
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.services import questionnaire_service as svc
from app.ai.modules.questionnaire_ai import get_next_question, QUESTION_BANK, USER_TYPE_QUESTIONS

router = APIRouter(prefix="/api/questionnaire", tags=["questionnaire"])


class AnswerRequest(BaseModel):
    step_id: str
    question_text: str
    answer_value: str
    answer_type: str = "text"


class ImportRequest(BaseModel):
    raw_text: str


@router.post("/import")
async def import_from_existing_profile(
    req: ImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Skip the questionnaire — import a CV or LinkedIn export directly."""
    from app.ai.modules.import_ai import extract_profile_from_text
    from app.models.profile import UserProfile, LinkedInProfile

    if len(req.raw_text.strip()) < 100:
        raise HTTPException(status_code=400, detail="Profile text too short — paste your full CV or LinkedIn export")

    extracted = await extract_profile_from_text(req.raw_text, current_user.user_type)

    up_data = extracted.get("user_profile", {})
    li_data = extracted.get("linkedin_profile", {})

    # Save / update UserProfile
    existing_up = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    json_fields = {"target_audience", "pain_points", "achievements", "keywords"}

    def _encode(key, val):
        return json.dumps(val) if isinstance(val, (list, dict)) else val

    if existing_up:
        for k, v in up_data.items():
            if hasattr(existing_up, k) and v is not None:
                setattr(existing_up, k, _encode(k, v))
        existing_up.raw_answers = json.dumps({"imported": True, "source": req.raw_text[:500]})
        existing_up.profile_version += 1
        db.commit()
        user_profile = existing_up
    else:
        up_kwargs = {k: _encode(k, v) for k, v in up_data.items() if v is not None}
        user_profile = UserProfile(
            user_id=current_user.id,
            raw_answers=json.dumps({"imported": True, "source": req.raw_text[:500]}),
            **up_kwargs,
        )
        db.add(user_profile)
        db.commit()
        db.refresh(user_profile)

    # Save / update LinkedInProfile
    existing_li = db.query(LinkedInProfile).filter(
        LinkedInProfile.user_id == current_user.id,
        LinkedInProfile.is_active == True,
    ).first()

    experience = li_data.get("experience", [])
    skills = li_data.get("skills", [])
    skills_categorized = li_data.get("skills_categorized", {})
    education = li_data.get("education", [])
    certifications = li_data.get("certifications", [])

    li_fields = {
        "headline": li_data.get("headline", ""),
        "about_section": li_data.get("about_section", ""),
        "experience_json": json.dumps(experience),
        "skills_json": json.dumps(skills),
        "skills_categorized_json": json.dumps(skills_categorized),
        "education_json": json.dumps(education),
        "certifications_json": json.dumps(certifications),
    }

    if existing_li:
        for k, v in li_fields.items():
            setattr(existing_li, k, v)
        existing_li.version += 1
        db.commit()
        li_profile = existing_li
    else:
        li_profile = LinkedInProfile(user_id=current_user.id, is_active=True, version=1, **li_fields)
        db.add(li_profile)
        db.commit()
        db.refresh(li_profile)

    return {
        "message": "Profile imported successfully",
        "user_profile_id": user_profile.id,
        "linkedin_profile_id": li_profile.id,
        "skills_count": len(skills),
        "experience_count": len(experience),
        "categories_count": len(skills_categorized),
    }



@router.post("/start")
async def start_questionnaire(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = svc.create_session(db, current_user)
    first_question = await get_next_question(
        user_type=current_user.user_type,
        answers={},
        step_number=0,
    )
    return {
        "session_token": session.session_token,
        "current_step": 0,
        "total_steps": 35,
        "first_question": first_question,
    }


@router.get("/session/{token}")
def get_session(
    token: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = svc.get_session(db, token)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_token": session.session_token,
        "status": session.status,
        "current_step": session.current_step,
        "total_steps": session.total_steps,
        "answers": svc.get_answers(session),
    }


@router.post("/session/{token}/answer")
async def submit_answer(
    token: str,
    req: AnswerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = svc.get_session(db, token)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    svc.save_answer(db, session, req.step_id, req.question_text, req.answer_value, req.answer_type)

    all_questions = QUESTION_BANK + USER_TYPE_QUESTIONS.get(current_user.user_type, [])
    is_done = session.current_step >= len(all_questions)

    if is_done:
        return {"done": True, "current_step": session.current_step, "total_steps": session.total_steps}

    answers = svc.get_answers(session)
    next_q = await get_next_question(
        user_type=current_user.user_type,
        answers=answers,
        step_number=session.current_step,
    )
    return {
        "done": False,
        "current_step": session.current_step,
        "total_steps": session.total_steps,
        "next_question": next_q,
    }


@router.post("/session/{token}/complete")
async def complete_questionnaire(
    token: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = svc.get_session(db, token)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    profile = await svc.complete_session(db, session, current_user)
    return {"message": "Profile synthesized successfully", "profile_id": profile.id}


@router.get("/session/{token}/summary")
def get_summary(
    token: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = svc.get_session(db, token)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "status": session.status,
        "answers": svc.get_answers(session),
        "current_step": session.current_step,
    }

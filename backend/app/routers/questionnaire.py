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

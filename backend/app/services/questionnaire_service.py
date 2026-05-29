import json
import secrets
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.questionnaire import QuestionnaireSession, QuestionnaireAnswer
from app.models.profile import UserProfile
from app.models.user import User
from app.ai.modules.questionnaire_ai import get_next_question, synthesize_profile, QUESTION_BANK, USER_TYPE_QUESTIONS


def create_session(db: Session, user: User) -> QuestionnaireSession:
    session = QuestionnaireSession(
        user_id=user.id,
        session_token=secrets.token_urlsafe(32),
        status="in_progress",
        current_step=0,
        answers="{}",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session(db: Session, token: str) -> QuestionnaireSession | None:
    return db.query(QuestionnaireSession).filter(
        QuestionnaireSession.session_token == token
    ).first()


def get_answers(session: QuestionnaireSession) -> dict:
    try:
        return json.loads(session.answers or "{}")
    except json.JSONDecodeError:
        return {}


def save_answer(
    db: Session,
    session: QuestionnaireSession,
    step_id: str,
    question_text: str,
    answer_value: str,
    answer_type: str = "text",
) -> None:
    answers = get_answers(session)
    answers[step_id] = answer_value
    session.answers = json.dumps(answers)
    session.current_step += 1

    log = QuestionnaireAnswer(
        session_id=session.id,
        step_id=step_id,
        question_text=question_text,
        answer_value=answer_value,
        answer_type=answer_type,
    )
    db.add(log)
    db.commit()


def is_complete(session: QuestionnaireSession) -> bool:
    total = QUESTION_BANK + USER_TYPE_QUESTIONS.get("founder", [])
    return session.current_step >= len(total)


async def complete_session(db: Session, session: QuestionnaireSession, user: User) -> UserProfile:
    answers = get_answers(session)
    synthesized = await synthesize_profile(user.user_type, answers)

    existing = db.query(UserProfile).filter(UserProfile.user_id == user.id).first()
    if existing:
        for key, value in synthesized.items():
            if isinstance(value, (list, dict)):
                setattr(existing, key, json.dumps(value))
            else:
                setattr(existing, key, value)
        existing.raw_answers = json.dumps(answers)
        existing.profile_version += 1
        db.commit()
        profile = existing
    else:
        profile_data = {}
        for key, value in synthesized.items():
            if isinstance(value, (list, dict)):
                profile_data[key] = json.dumps(value)
            else:
                profile_data[key] = value

        profile = UserProfile(
            user_id=user.id,
            raw_answers=json.dumps(answers),
            **profile_data,
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)

    session.status = "completed"
    session.completed_at = datetime.utcnow()
    db.commit()
    return profile

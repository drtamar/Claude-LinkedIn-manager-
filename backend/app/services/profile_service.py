import json
from sqlalchemy.orm import Session
from app.models.profile import UserProfile, LinkedInProfile
from app.models.user import User
from app.ai.modules.profile_ai import (
    generate_headline, generate_experience, generate_skills, score_profile
)


def get_user_profile(db: Session, user_id: int) -> UserProfile | None:
    return db.query(UserProfile).filter(UserProfile.user_id == user_id).first()


def get_linkedin_profile(db: Session, user_id: int) -> LinkedInProfile | None:
    return db.query(LinkedInProfile).filter(
        LinkedInProfile.user_id == user_id,
        LinkedInProfile.is_active == True
    ).first()


def user_profile_to_dict(profile: UserProfile) -> dict:
    if not profile:
        return {}
    result = {}
    json_fields = ["goals", "target_audience", "pain_points", "achievements", "keywords", "competitors"]
    for field in json_fields:
        val = getattr(profile, field, None)
        if val:
            try:
                result[field] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                result[field] = val
        else:
            result[field] = [] if field != "target_audience" else {}

    for field in ["industry", "sub_industry", "content_tone", "posting_frequency",
                  "career_stage", "unique_value_prop", "brand_voice_notes", "geographic_focus"]:
        result[field] = getattr(profile, field, None) or ""

    return result


async def generate_full_profile(db: Session, user: User) -> LinkedInProfile:
    user_profile = get_user_profile(db, user.id)
    profile_dict = user_profile_to_dict(user_profile)

    headline_data = await generate_headline(profile_dict)
    variants = headline_data.get("variants", [])
    headline = variants[0]["headline"] if variants else f"{user.display_name} | {profile_dict.get('industry', '')}"

    experience_data = await generate_experience(profile_dict)
    skills = await generate_skills(profile_dict)

    score_data = await score_profile(
        headline=headline,
        about="",  # about will be streamed separately
        skills=skills,
        experience=experience_data.get("experiences", []),
    )

    existing = get_linkedin_profile(db, user.id)
    if existing:
        existing.is_active = False
        db.commit()

    li_profile = LinkedInProfile(
        user_id=user.id,
        headline=headline,
        headline_variants=json.dumps([v["headline"] for v in variants]),
        experience_json=json.dumps(experience_data.get("experiences", [])),
        skills_json=json.dumps(skills),
        profile_score=score_data.get("total_score", 0),
        score_breakdown=json.dumps(score_data.get("breakdown", {})),
        is_active=True,
    )
    db.add(li_profile)
    db.commit()
    db.refresh(li_profile)
    return li_profile


def update_profile_section(db: Session, user_id: int, section: str, content: str) -> LinkedInProfile:
    profile = get_linkedin_profile(db, user_id)
    if not profile:
        raise ValueError("LinkedIn profile not found")
    setattr(profile, section, content)
    db.commit()
    db.refresh(profile)
    return profile

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    goals = Column(Text)  # JSON array
    industry = Column(String)
    sub_industry = Column(String)
    target_audience = Column(Text)  # JSON
    content_tone = Column(String, default="professional")
    posting_frequency = Column(String, default="3x_week")
    career_stage = Column(String, default="mid")
    company_size_focus = Column(String)
    geographic_focus = Column(String)
    unique_value_prop = Column(Text)
    pain_points = Column(Text)  # JSON array
    achievements = Column(Text)  # JSON array
    keywords = Column(Text)  # JSON array
    competitors = Column(Text)  # JSON array
    brand_voice_notes = Column(Text)
    raw_answers = Column(Text)  # JSON full questionnaire responses
    profile_version = Column(Integer, default=1)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    user = relationship("User", back_populates="profile")


class LinkedInProfile(Base):
    __tablename__ = "linkedin_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    version = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    headline = Column(String)
    headline_variants = Column(Text)  # JSON array of 3
    about_section = Column(Text)
    about_variants = Column(Text)  # JSON array of 2
    banner_text = Column(Text)
    experience_json = Column(Text)  # JSON array
    skills_json = Column(Text)  # JSON array of up to 50
    featured_json = Column(Text)  # JSON array
    education_json = Column(Text)
    certifications_json = Column(Text)
    contact_info_json = Column(Text)
    profile_score = Column(Integer, default=0)
    score_breakdown = Column(Text)  # JSON
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    user = relationship("User", back_populates="linkedin_profiles")

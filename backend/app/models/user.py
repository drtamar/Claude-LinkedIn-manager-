from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    display_name = Column(String)
    user_type = Column(String, nullable=False, default="founder")  # job_seeker|founder|sales|creator
    is_active = Column(Boolean, default=True)
    linkedin_cookies = Column(Text)  # AES-encrypted JSON
    linkedin_connected = Column(Boolean, default=False)
    linkedin_url = Column(String)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    profile = relationship("UserProfile", back_populates="user", uselist=False)
    linkedin_profiles = relationship("LinkedInProfile", back_populates="user")
    questionnaire_sessions = relationship("QuestionnaireSession", back_populates="user")
    posts = relationship("Post", back_populates="user")
    icp_profiles = relationship("ICPProfile", back_populates="user")
    connection_requests = relationship("ConnectionRequest", back_populates="user")
    ssi_scores = relationship("SSIScore", back_populates="user")
    learning_cycles = relationship("LearningCycle", back_populates="user")
    automation_jobs = relationship("AutomationJob", back_populates="user")

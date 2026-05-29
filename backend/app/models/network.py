from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class ICPProfile(Base):
    __tablename__ = "icp_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    job_titles = Column(Text)  # JSON array
    industries = Column(Text)  # JSON array
    company_sizes = Column(Text)  # JSON array
    seniority_levels = Column(Text)  # JSON array
    geographies = Column(Text)  # JSON array
    keywords_to_match = Column(Text)  # JSON array
    keywords_to_exclude = Column(Text)  # JSON array
    pain_points = Column(Text)  # JSON array
    connection_note_template = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="icp_profiles")
    connections = relationship("ConnectionRequest", back_populates="icp")


class ConnectionRequest(Base):
    __tablename__ = "connection_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    icp_id = Column(Integer, ForeignKey("icp_profiles.id"), nullable=True)
    linkedin_profile_url = Column(String, nullable=False)
    prospect_name = Column(String)
    prospect_title = Column(String)
    prospect_company = Column(String)
    connection_note = Column(Text)
    status = Column(String, default="queued")  # queued|sent|accepted|declined|withdrawn
    sequence_step = Column(Integer, default=1)
    sent_at = Column(DateTime)
    accepted_at = Column(DateTime)
    follow_up_1_at = Column(DateTime)
    follow_up_2_at = Column(DateTime)
    follow_up_sent = Column(Boolean, default=False)
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="connection_requests")
    icp = relationship("ICPProfile", back_populates="connections")


class OutreachSequence(Base):
    __tablename__ = "outreach_sequences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    icp_id = Column(Integer, ForeignKey("icp_profiles.id"), nullable=True)
    name = Column(String, nullable=False)
    step_1_message = Column(Text)  # connection note
    step_2_delay_days = Column(Integer, default=3)
    step_2_message = Column(Text)
    step_3_delay_days = Column(Integer, default=7)
    step_3_message = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

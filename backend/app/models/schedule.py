from sqlalchemy import Column, Integer, String, Text, Date, Time, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class ContentCalendar(Base):
    __tablename__ = "content_calendar"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=True)
    idea_id = Column(Integer, ForeignKey("content_ideas.id"), nullable=True)
    scheduled_date = Column(Date, nullable=False)
    scheduled_time = Column(Time)
    slot_type = Column(String, default="morning")  # morning|lunch|evening
    optimal_score = Column(Float, default=0.0)
    status = Column(String, default="planned")  # planned|confirmed|published|missed
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

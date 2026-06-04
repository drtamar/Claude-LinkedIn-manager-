from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class SSIScore(Base):
    __tablename__ = "ssi_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    score_date = Column(Date, nullable=False)
    total_score = Column(Integer, default=0)
    establish_brand = Column(Integer, default=0)
    find_right_people = Column(Integer, default=0)
    engage_insights = Column(Integer, default=0)
    build_relationships = Column(Integer, default=0)
    industry_rank = Column(Integer)
    network_rank = Column(Integer)
    scraped_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="ssi_scores")


class NetworkStats(Base):
    __tablename__ = "network_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    snapshot_date = Column(Date, nullable=False)
    total_connections = Column(Integer, default=0)
    new_connections = Column(Integer, default=0)
    profile_views_7d = Column(Integer, default=0)
    search_appearances_7d = Column(Integer, default=0)
    post_impressions_30d = Column(Integer, default=0)
    followers = Column(Integer, default=0)

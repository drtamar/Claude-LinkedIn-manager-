import json
from sqlalchemy.orm import Session
from app.models.network import ICPProfile, ConnectionRequest, OutreachSequence


def get_icps(db: Session, user_id: int) -> list[ICPProfile]:
    return db.query(ICPProfile).filter(ICPProfile.user_id == user_id).all()


def create_icp(db: Session, user_id: int, data: dict) -> ICPProfile:
    icp = ICPProfile(
        user_id=user_id,
        name=data["name"],
        job_titles=json.dumps(data.get("job_titles", [])),
        industries=json.dumps(data.get("industries", [])),
        company_sizes=json.dumps(data.get("company_sizes", [])),
        seniority_levels=json.dumps(data.get("seniority_levels", [])),
        geographies=json.dumps(data.get("geographies", [])),
        keywords_to_match=json.dumps(data.get("keywords_to_match", [])),
        keywords_to_exclude=json.dumps(data.get("keywords_to_exclude", [])),
        pain_points=json.dumps(data.get("pain_points", [])),
        connection_note_template=data.get("connection_note_template", ""),
    )
    db.add(icp)
    db.commit()
    db.refresh(icp)
    return icp


def get_connections(db: Session, user_id: int, status: str = None) -> list[ConnectionRequest]:
    q = db.query(ConnectionRequest).filter(ConnectionRequest.user_id == user_id)
    if status:
        q = q.filter(ConnectionRequest.status == status)
    return q.order_by(ConnectionRequest.created_at.desc()).all()


def add_connection(db: Session, user_id: int, data: dict) -> ConnectionRequest:
    conn = ConnectionRequest(
        user_id=user_id,
        icp_id=data.get("icp_id"),
        linkedin_profile_url=data["linkedin_profile_url"],
        prospect_name=data.get("prospect_name", ""),
        prospect_title=data.get("prospect_title", ""),
        prospect_company=data.get("prospect_company", ""),
        connection_note=data.get("connection_note", ""),
        status="queued",
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return conn


def get_sequences(db: Session, user_id: int) -> list[OutreachSequence]:
    return db.query(OutreachSequence).filter(OutreachSequence.user_id == user_id).all()


def create_sequence(db: Session, user_id: int, data: dict) -> OutreachSequence:
    seq = OutreachSequence(
        user_id=user_id,
        icp_id=data.get("icp_id"),
        name=data["name"],
        step_1_message=data.get("step_1_message", ""),
        step_2_delay_days=data.get("step_2_delay_days", 3),
        step_2_message=data.get("step_2_message", ""),
        step_3_delay_days=data.get("step_3_delay_days", 7),
        step_3_message=data.get("step_3_message", ""),
    )
    db.add(seq)
    db.commit()
    db.refresh(seq)
    return seq

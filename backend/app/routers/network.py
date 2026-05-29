import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.services import network_service as svc
from app.services.profile_service import get_user_profile, user_profile_to_dict
from app.ai.modules.network_ai import stream_icp, generate_connection_note, stream_sequence

router = APIRouter(prefix="/api/network", tags=["network"])


class ICPCreateRequest(BaseModel):
    name: str
    job_titles: list[str] = []
    industries: list[str] = []
    company_sizes: list[str] = []
    seniority_levels: list[str] = []
    geographies: list[str] = []
    keywords_to_match: list[str] = []
    keywords_to_exclude: list[str] = []
    pain_points: list[str] = []
    connection_note_template: str = ""


class ConnectionRequest(BaseModel):
    linkedin_profile_url: str
    prospect_name: Optional[str] = None
    prospect_title: Optional[str] = None
    prospect_company: Optional[str] = None
    connection_note: Optional[str] = None
    icp_id: Optional[int] = None


class NoteRequest(BaseModel):
    prospect_name: str
    prospect_title: str
    prospect_company: str
    prospect_bio: Optional[str] = None


class SequenceCreateRequest(BaseModel):
    name: str
    icp_id: Optional[int] = None
    step_1_message: str = ""
    step_2_delay_days: int = 3
    step_2_message: str = ""
    step_3_delay_days: int = 7
    step_3_message: str = ""


class GenerateSequenceRequest(BaseModel):
    icp_name: str
    icp_description: str = ""


@router.get("/icp")
def list_icps(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    icps = svc.get_icps(db, current_user.id)
    return [
        {
            "id": i.id,
            "name": i.name,
            "job_titles": json.loads(i.job_titles or "[]"),
            "industries": json.loads(i.industries or "[]"),
            "keywords_to_match": json.loads(i.keywords_to_match or "[]"),
            "connection_note_template": i.connection_note_template,
            "is_active": i.is_active,
        }
        for i in icps
    ]


@router.post("/icp")
def create_icp(
    req: ICPCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    icp = svc.create_icp(db, current_user.id, req.model_dump())
    return {"id": icp.id, "name": icp.name}


@router.post("/icp/generate")
async def generate_icp(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user_profile_obj = get_user_profile(db, current_user.id)
    if not user_profile_obj:
        raise HTTPException(status_code=400, detail="Complete onboarding first")
    profile_dict = user_profile_to_dict(user_profile_obj)

    async def stream():
        async for token in stream_icp(profile_dict):
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.get("/connections")
def list_connections(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conns = svc.get_connections(db, current_user.id, status)
    return [
        {
            "id": c.id,
            "linkedin_profile_url": c.linkedin_profile_url,
            "prospect_name": c.prospect_name,
            "prospect_title": c.prospect_title,
            "prospect_company": c.prospect_company,
            "connection_note": c.connection_note,
            "status": c.status,
            "sent_at": c.sent_at.isoformat() if c.sent_at else None,
            "accepted_at": c.accepted_at.isoformat() if c.accepted_at else None,
        }
        for c in conns
    ]


@router.post("/connections")
def add_connection(
    req: ConnectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conn = svc.add_connection(db, current_user.id, req.model_dump())
    return {"id": conn.id, "status": conn.status}


@router.post("/connections/generate-note")
async def gen_connection_note(
    req: NoteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user_profile_obj = get_user_profile(db, current_user.id)
    profile_dict = user_profile_to_dict(user_profile_obj) if user_profile_obj else {}
    note = await generate_connection_note(
        prospect_name=req.prospect_name,
        prospect_title=req.prospect_title,
        prospect_company=req.prospect_company,
        prospect_bio_snippet=req.prospect_bio or "",
        user_profile=profile_dict,
    )
    return {"note": note, "character_count": len(note)}


@router.get("/sequences")
def list_sequences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    seqs = svc.get_sequences(db, current_user.id)
    return [
        {
            "id": s.id,
            "name": s.name,
            "icp_id": s.icp_id,
            "step_1_message": s.step_1_message,
            "step_2_delay_days": s.step_2_delay_days,
            "step_2_message": s.step_2_message,
            "step_3_delay_days": s.step_3_delay_days,
            "step_3_message": s.step_3_message,
            "is_active": s.is_active,
        }
        for s in seqs
    ]


@router.post("/sequences")
def create_sequence(
    req: SequenceCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    seq = svc.create_sequence(db, current_user.id, req.model_dump())
    return {"id": seq.id, "name": seq.name}


@router.post("/sequences/generate")
async def generate_sequence(
    req: GenerateSequenceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user_profile_obj = get_user_profile(db, current_user.id)
    profile_dict = user_profile_to_dict(user_profile_obj) if user_profile_obj else {}

    async def stream():
        async for token in stream_sequence(profile_dict, req.icp_name, req.icp_description):
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")

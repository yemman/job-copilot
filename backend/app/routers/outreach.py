from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ActivityLog, Application, Contact, OutreachMessage, Profile
from app.schemas import (
    OutreachDraftRequest,
    OutreachMessageOut,
    OutreachReplyRequest,
    OutreachUpdateRequest,
)
from app.services.learning import record_feedback_and_learn
from app.services.outreach import draft_outreach_message

router = APIRouter(tags=["outreach"])


@router.post("/api/applications/{application_id}/outreach/draft", response_model=OutreachMessageOut, status_code=201)
def create_outreach_draft(
    application_id: int,
    payload: OutreachDraftRequest,
    db: Session = Depends(get_db),
):
    app_obj = db.query(Application).filter(Application.id == application_id).first()
    if not app_obj or not app_obj.job:
        raise HTTPException(status_code=404, detail="Application not found")

    contact: Contact | None = None
    if payload.contact_id is not None:
        contact = db.query(Contact).filter(Contact.id == payload.contact_id).first()
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")

    profile = db.query(Profile).first() or Profile()
    contact_name = (contact.name if contact else payload.contact_name.strip()) or "Team Member"
    drafted = draft_outreach_message(
        job=app_obj.job,
        profile=profile,
        contact=contact,
        contact_name=contact_name,
        channel=payload.channel,
    )

    msg = OutreachMessage(
        application_id=app_obj.id,
        contact_id=contact.id if contact else None,
        contact_name_snapshot=contact_name,
        channel=payload.channel,
        subject=drafted["subject"],
        body=drafted["body"],
        status="draft",
    )
    db.add(msg)

    if app_obj.stage == "connection_search":
        app_obj.stage = "outreach_drafted"
        app_obj.next_step = f"Review, approve, and send outreach to {contact_name}"

    db.add(
        ActivityLog(
            application_id=app_obj.id,
            action="outreach_drafted",
            details=f"Drafted {payload.channel} outreach for {contact_name} (status: draft, awaiting HITL approval).",
        )
    )
    db.commit()
    db.refresh(msg)
    return msg


@router.patch("/api/outreach/{outreach_id}", response_model=OutreachMessageOut)
def update_outreach(
    outreach_id: int, payload: OutreachUpdateRequest, db: Session = Depends(get_db)
):
    msg = db.query(OutreachMessage).filter(OutreachMessage.id == outreach_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Outreach message not found")

    data = payload.model_dump(exclude_unset=True)
    for key, val in data.items():
        setattr(msg, key, val)

    # Editing an approved draft resets approval so a human must re-approve before sending
    if msg.status == "approved":
        msg.status = "draft"
        msg.approved_at = None

    db.commit()
    db.refresh(msg)
    return msg


@router.post("/api/outreach/{outreach_id}/approve", response_model=OutreachMessageOut)
def approve_outreach(outreach_id: int, db: Session = Depends(get_db)):
    msg = db.query(OutreachMessage).filter(OutreachMessage.id == outreach_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Outreach message not found")
    if msg.channel == "linkedin_connect_note" and len(msg.body or "") > 300:
        raise HTTPException(
            status_code=400,
            detail="LinkedIn connection note exceeds 300 characters. Please shorten it before approving.",
        )

    msg.status = "approved"
    msg.approved_at = datetime.now(timezone.utc)
    db.add(
        ActivityLog(
            application_id=msg.application_id,
            action="outreach_approved",
            details=f"Approved {msg.channel} draft for {msg.contact_name_snapshot}. Ready to copy and send manually.",
        )
    )
    db.commit()
    db.refresh(msg)
    return msg


@router.post("/api/outreach/{outreach_id}/mark-sent", response_model=OutreachMessageOut)
def mark_outreach_sent(outreach_id: int, db: Session = Depends(get_db)):
    msg = db.query(OutreachMessage).filter(OutreachMessage.id == outreach_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Outreach message not found")
    if msg.status != "approved":
        raise HTTPException(
            status_code=400,
            detail="Human-in-the-loop gate: Outreach draft must be approved before marking as sent.",
        )

    now = datetime.now(timezone.utc)
    msg.status = "sent"
    msg.sent_at = now
    msg.follow_up_at = now + timedelta(days=3)

    app_obj = msg.application
    if app_obj and app_obj.stage in {"connection_search", "outreach_drafted"}:
        app_obj.stage = "outreach_sent"
        app_obj.next_step = f"Wait for reply / follow up with {msg.contact_name_snapshot}"
        app_obj.next_step_at = msg.follow_up_at

    db.add(
        ActivityLog(
            application_id=msg.application_id,
            action="outreach_sent",
            details=f"Marked {msg.channel} outreach to {msg.contact_name_snapshot} as sent. Follow-up set in 3 days.",
        )
    )
    db.commit()
    db.refresh(msg)
    return msg


@router.post("/api/outreach/{outreach_id}/log-reply", response_model=OutreachMessageOut)
def log_outreach_reply(
    outreach_id: int, payload: OutreachReplyRequest, db: Session = Depends(get_db)
):
    msg = db.query(OutreachMessage).filter(OutreachMessage.id == outreach_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Outreach message not found")

    msg.status = "replied" if payload.replied else "no_response"
    msg.reply_notes = payload.reply_notes.strip()

    app_obj = msg.application
    if app_obj and payload.advance_to_ready_to_apply:
        app_obj.stage = "ready_to_apply"
        app_obj.next_step = "Submit formal application (connection outreach complete)"

    db.add(
        ActivityLog(
            application_id=msg.application_id,
            action="outreach_replied" if payload.replied else "outreach_no_response",
            details=payload.reply_notes or f"Logged {msg.status} for {msg.contact_name_snapshot}.",
        )
    )
    db.commit()

    if payload.replied and app_obj:
        record_feedback_and_learn(
            db,
            event_type="outreach_replied",
            job=app_obj.job,
            application=app_obj,
            note=payload.reply_notes,
        )

    db.refresh(msg)
    return msg

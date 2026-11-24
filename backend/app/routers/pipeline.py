from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ActivityLog, Application, OutreachMessage
from app.schemas import (
    ApplicationOut,
    ApplicationTransitionRequest,
    ApplicationUpdate,
)
from app.services.learning import record_feedback_and_learn
from app.services.outreach import find_matching_contacts

router = APIRouter(prefix="/api/applications", tags=["pipeline"])

CONNECTION_FIRST_STAGES = {"ready_to_apply", "applied"}
LEARNING_STAGE_MAP = {
    "interviewing": "interview_invited",
    "offer": "offer_received",
    "rejected": "application_rejected",
    "withdrawn": "application_withdrawn",
}


def _serialize_application(db: Session, app_obj: Application) -> ApplicationOut:
    matched = find_matching_contacts(db, app_obj.job.company) if app_obj.job else []
    out = ApplicationOut.model_validate(app_obj)
    out.matched_contacts_count = len(matched)
    return out


@router.get("", response_model=list[ApplicationOut])
def list_applications(stage: str | None = Query(default=None), db: Session = Depends(get_db)):
    q = db.query(Application)
    if stage:
        q = q.filter(Application.stage == stage)
    apps = q.order_by(Application.updated_at.desc()).all()
    return [_serialize_application(db, a) for a in apps]


@router.get("/{application_id}", response_model=ApplicationOut)
def get_application(application_id: int, db: Session = Depends(get_db)):
    app_obj = db.query(Application).filter(Application.id == application_id).first()
    if not app_obj:
        raise HTTPException(status_code=404, detail="Application not found")
    return _serialize_application(db, app_obj)


@router.patch("/{application_id}", response_model=ApplicationOut)
def update_application(
    application_id: int, payload: ApplicationUpdate, db: Session = Depends(get_db)
):
    app_obj = db.query(Application).filter(Application.id == application_id).first()
    if not app_obj:
        raise HTTPException(status_code=404, detail="Application not found")
    for key, val in payload.model_dump(exclude_unset=True).items():
        setattr(app_obj, key, val)
    db.commit()
    db.refresh(app_obj)
    return _serialize_application(db, app_obj)


@router.post("/{application_id}/transition", response_model=ApplicationOut)
def transition_application(
    application_id: int,
    payload: ApplicationTransitionRequest,
    db: Session = Depends(get_db),
):
    app_obj = db.query(Application).filter(Application.id == application_id).first()
    if not app_obj:
        raise HTTPException(status_code=404, detail="Application not found")

    target_stage = payload.stage
    has_sent_outreach = (
        db.query(OutreachMessage)
        .filter(
            OutreachMessage.application_id == app_obj.id,
            OutreachMessage.status.in_(["sent", "replied"]),
        )
        .count()
        > 0
    )

    if target_stage in CONNECTION_FIRST_STAGES and not has_sent_outreach:
        reason = (payload.connection_override_reason or app_obj.connection_override_reason or "").strip()
        if not reason:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Connection-first gate: Please draft and mark at least one outreach message as sent first, "
                    "or provide a connection_override_reason (e.g. 'No connection found')."
                ),
            )
        app_obj.connection_override_reason = reason

    prev_stage = app_obj.stage
    app_obj.stage = target_stage
    if target_stage == "applied" and app_obj.applied_at is None:
        app_obj.applied_at = datetime.now(timezone.utc)
    if payload.outcome_reason:
        app_obj.outcome_reason = payload.outcome_reason

    detail_msg = f"Moved from {prev_stage} to {target_stage}."
    if payload.connection_override_reason:
        detail_msg += f" Override: {payload.connection_override_reason}"
    if payload.outcome_reason:
        detail_msg += f" Reason: {payload.outcome_reason}"
    if payload.note:
        detail_msg += f" Note: {payload.note}"

    db.add(
        ActivityLog(
            application_id=app_obj.id,
            action=f"stage_{target_stage}",
            details=detail_msg,
        )
    )
    db.commit()
    db.refresh(app_obj)

    if target_stage in LEARNING_STAGE_MAP and prev_stage != target_stage:
        record_feedback_and_learn(
            db,
            event_type=LEARNING_STAGE_MAP[target_stage],
            job=app_obj.job,
            application=app_obj,
            reason_code=payload.outcome_reason,
            note=payload.note,
        )
        db.refresh(app_obj)

    return _serialize_application(db, app_obj)

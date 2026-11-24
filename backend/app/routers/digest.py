from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import ActivityLog, Application, DailyDigest, DailyDigestItem, Profile
from app.schemas import (
    DailyDigestOut,
    DigestDecisionRequest,
    DigestGenerateRequest,
    DigestTodayResponse,
)
from app.services.digest import (
    DEFAULT_DIGEST_DAYS,
    generate_daily_digest,
    get_day_code,
    get_local_now,
    get_next_digest_day_label,
    is_digest_day,
)
from app.services.learning import record_feedback_and_learn

router = APIRouter(tags=["digest"])


@router.get("/api/digests/today", response_model=DigestTodayResponse)
def get_today_digest(db: Session = Depends(get_db)):
    profile = db.query(Profile).first()
    tz = profile.timezone if profile else "Asia/Jerusalem"
    digest_days = (profile.digest_days if profile and profile.digest_days else DEFAULT_DIGEST_DAYS)
    now = get_local_now(tz)
    date_str = now.strftime("%Y-%m-%d")
    day_code = get_day_code(now)

    digest = db.query(DailyDigest).filter(DailyDigest.digest_date == date_str).first()
    return DigestTodayResponse(
        today_date=date_str,
        day_of_week=day_code,
        is_scheduled_day=is_digest_day(now, digest_days),
        digest_days=digest_days,
        next_digest_day=get_next_digest_day_label(now, digest_days),
        digest=DailyDigestOut.model_validate(digest) if digest else None,
    )


@router.get("/api/digests", response_model=list[DailyDigestOut])
def list_digests(db: Session = Depends(get_db)):
    return db.query(DailyDigest).order_by(DailyDigest.digest_date.desc()).limit(20).all()


@router.post("/api/digests/generate")
def trigger_generate_digest(payload: DigestGenerateRequest, db: Session = Depends(get_db)):
    res = generate_daily_digest(db, force=payload.force, sync_sources=payload.sync_sources)
    digest_obj = res.get("digest")
    return {
        "skipped": res["skipped"],
        "already_existed": res.get("already_existed", False),
        "reason": res["reason"],
        "sync_results": res.get("sync_results", []),
        "digest": DailyDigestOut.model_validate(digest_obj) if digest_obj else None,
    }


@router.post("/api/cron/daily-digest")
def cron_daily_digest(
    x_cron_secret: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    expected = get_settings().cron_secret
    if expected and x_cron_secret != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Cron-Secret")
    res = generate_daily_digest(db, force=False, sync_sources=True)
    digest_obj = res.get("digest")
    return {
        "skipped": res["skipped"],
        "reason": res["reason"],
        "sync_results": res.get("sync_results", []),
        "digest": DailyDigestOut.model_validate(digest_obj) if digest_obj else None,
    }


@router.post("/api/digests/items/{item_id}/decide")
def decide_digest_item(
    item_id: int, payload: DigestDecisionRequest, db: Session = Depends(get_db)
):
    item = db.query(DailyDigestItem).filter(DailyDigestItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Digest item not found")

    job = item.job
    now = datetime.now(timezone.utc)
    item.decision = payload.decision
    item.decided_at = now

    application_id: int | None = None
    if payload.decision == "approved":
        job.status = "approved"
        existing_app = db.query(Application).filter(Application.job_id == job.id).first()
        if existing_app is None:
            app_obj = Application(
                job_id=job.id,
                stage="connection_search",
                next_step=f"Find a connection at {job.company} before applying",
            )
            db.add(app_obj)
            db.flush()
            db.add(
                ActivityLog(
                    application_id=app_obj.id,
                    action="digest_approved",
                    details=f"Approved from daily digest; entered connection-first gate for {job.company}.",
                )
            )
            application_id = app_obj.id
        else:
            application_id = existing_app.id
        db.commit()
        _, touched_rules = record_feedback_and_learn(
            db,
            event_type="digest_approve",
            job=job,
            reason_code=payload.reason_code,
            note=payload.note,
        )
    else:
        job.status = "skipped"
        db.commit()
        _, touched_rules = record_feedback_and_learn(
            db,
            event_type="digest_skip",
            job=job,
            reason_code=payload.reason_code or "other",
            note=payload.note,
        )

    return {
        "item_id": item.id,
        "decision": item.decision,
        "application_id": application_id,
        "learned_rules_updated": len(touched_rules),
    }

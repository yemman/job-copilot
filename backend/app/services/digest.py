from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models import DailyDigest, DailyDigestItem, FeedbackEvent, Job, LearnedRule, Profile
from app.services.job_sources import sync_all_enabled_sources
from app.services.outreach import normalize_company_name
from app.services.scoring import score_job

DAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DEFAULT_DIGEST_DAYS = ["sun", "mon", "tue", "wed"]


def get_local_now(tz_name: str) -> datetime:
    try:
        tz = ZoneInfo(tz_name or "Asia/Jerusalem")
    except Exception:
        tz = ZoneInfo("UTC")
    return datetime.now(tz)


def get_day_code(dt: datetime) -> str:
    return DAY_NAMES[dt.weekday()]


def is_digest_day(dt: datetime, digest_days: list[str] | None) -> bool:
    allowed = {d.strip().lower() for d in (digest_days or DEFAULT_DIGEST_DAYS)}
    return get_day_code(dt) in allowed


def get_next_digest_day_label(dt: datetime, digest_days: list[str] | None) -> str:
    allowed = {d.strip().lower() for d in (digest_days or DEFAULT_DIGEST_DAYS)}
    if not allowed:
        allowed = set(DEFAULT_DIGEST_DAYS)
    for offset in range(0, 8):
        cand = dt + timedelta(days=offset)
        code = get_day_code(cand)
        if code in allowed:
            if offset == 0:
                return f"Today ({code.title()})"
            if offset == 1:
                return f"Tomorrow ({code.title()})"
            return f"{cand.strftime('%a %b %d')}"
    return "Sun"


def generate_daily_digest(
    db: Session,
    force: bool = False,
    sync_sources: bool = False,
    target_date: str | None = None,
    now_override: datetime | None = None,
) -> dict[str, Any]:
    profile = db.query(Profile).first()
    if profile is None:
        profile = Profile()
        db.add(profile)
        db.commit()
        db.refresh(profile)

    now = now_override or get_local_now(profile.timezone)
    day_code = get_day_code(now)
    date_str = target_date or now.strftime("%Y-%m-%d")
    scheduled_day = is_digest_day(now, profile.digest_days)

    if not scheduled_day and not force:
        return {
            "skipped": True,
            "reason": f"Today ({day_code.title()}) is outside your Sun–Wed schedule ({', '.join(profile.digest_days)}).",
            "digest": None,
            "sync_results": [],
        }

    existing = db.query(DailyDigest).filter(DailyDigest.digest_date == date_str).first()
    if existing and not force:
        return {
            "skipped": False,
            "already_existed": True,
            "reason": "Digest already generated for today.",
            "digest": existing,
            "sync_results": [],
        }

    sync_results = sync_all_enabled_sources(db) if sync_sources else []

    pick_count = max(3, min(5, int(profile.daily_pick_count or 4)))
    if existing and force:
        remaining = max(0, pick_count - len(existing.items))
        if remaining == 0:
            return {
                "skipped": False,
                "already_existed": True,
                "reason": "Today's digest already has all picks.",
                "digest": existing,
                "sync_results": sync_results,
            }
        target_slots = remaining
        digest = existing
        start_rank = len(existing.items) + 1
    else:
        target_slots = pick_count
        digest = DailyDigest(
            digest_date=date_str,
            day_of_week=day_code,
            scheduled=scheduled_day,
            notes="" if scheduled_day else "Generated manually on an off-schedule day.",
        )
        db.add(digest)
        db.flush()
        start_rank = 1

    candidates = db.query(Job).filter(Job.status == "new").all()
    if not candidates:
        if not existing:
            db.commit()
            db.refresh(digest)
        return {
            "skipped": False,
            "already_existed": False,
            "reason": "No new unscored/unseen jobs available. Sync a source or paste a job URL.",
            "digest": digest,
            "sync_results": sync_results,
        }

    learned_rules = db.query(LearnedRule).all()
    recent_feedback = (
        db.query(FeedbackEvent).order_by(FeedbackEvent.created_at.desc()).limit(15).all()
    )

    scored: list[tuple[Job, float, dict[str, Any]]] = []
    for job in candidates:
        s, bd = score_job(job, profile, learned_rules, recent_feedback, use_ai=True)
        job.score = s
        job.score_breakdown = bd
        scored.append((job, s, bd))

    scored.sort(key=lambda item: item[1], reverse=True)

    # Diversity: prefer at most 2 per company when enough jobs exist
    selected: list[tuple[Job, float, dict[str, Any]]] = []
    company_counts: dict[str, int] = {}
    deferred: list[tuple[Job, float, dict[str, Any]]] = []

    for entry in scored:
        comp_key = normalize_company_name(entry[0].company) or entry[0].company.lower()
        if company_counts.get(comp_key, 0) < 2:
            selected.append(entry)
            company_counts[comp_key] = company_counts.get(comp_key, 0) + 1
            if len(selected) >= target_slots:
                break
        else:
            deferred.append(entry)

    if len(selected) < target_slots:
        for entry in deferred:
            selected.append(entry)
            if len(selected) >= target_slots:
                break

    for offset, (job, s, bd) in enumerate(selected):
        job.status = "suggested"
        item = DailyDigestItem(
            digest_id=digest.id,
            job_id=job.id,
            rank=start_rank + offset,
            score_snapshot=s,
            rationale_snapshot=bd.get("rationale", ""),
            decision="pending",
        )
        db.add(item)

    db.commit()
    db.refresh(digest)
    return {
        "skipped": False,
        "already_existed": False,
        "reason": f"Selected {len(selected)} top jobs for {date_str}.",
        "digest": digest,
        "sync_results": sync_results,
    }

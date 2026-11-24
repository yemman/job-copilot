from datetime import datetime, timezone
import re
from sqlalchemy.orm import Session

from app.models import Application, FeedbackEvent, Job, LearnedRule, Profile
from app.services.outreach import normalize_company_name
from app.services.resume_parser import extract_skills_from_text

SENIORITY_KEYWORDS = ["principal", "staff", "lead", "manager", "director", "junior", "intern", "entry"]


def _clamp_weight(w: float) -> float:
    return round(max(-20.0, min(20.0, w)), 2)


def _upsert_rule(
    db: Session,
    category: str,
    term: str,
    delta: float,
    touched: list[LearnedRule],
) -> None:
    clean_term = term.strip()
    if not clean_term:
        return
    rule = (
        db.query(LearnedRule)
        .filter(LearnedRule.category == category, LearnedRule.term == clean_term)
        .first()
    )
    if rule:
        if rule.locked:
            return
        rule.weight = _clamp_weight(rule.weight + delta)
        rule.evidence_count = (rule.evidence_count or 0) + 1
        rule.updated_at = datetime.now(timezone.utc)
        touched.append(rule)
    else:
        rule = LearnedRule(
            category=category,
            term=clean_term[:150],
            weight=_clamp_weight(delta),
            evidence_count=1,
            source="learned",
            locked=False,
            enabled=True,
        )
        db.add(rule)
        db.flush()
        touched.append(rule)


def record_feedback_and_learn(
    db: Session,
    event_type: str,
    job: Job | None = None,
    application: Application | None = None,
    reason_code: str | None = None,
    note: str | None = None,
) -> tuple[FeedbackEvent, list[LearnedRule]]:
    if job is None and application is not None:
        job = application.job

    snapshot = {}
    if job is not None:
        snapshot = {
            "title": job.title,
            "company": job.company,
            "work_mode": job.work_mode,
            "location": job.location,
            "tags": job.tags or [],
        }

    fb = FeedbackEvent(
        job_id=job.id if job else None,
        application_id=application.id if application else None,
        event_type=event_type,
        reason_code=reason_code,
        note=note,
        job_snapshot=snapshot,
    )
    db.add(fb)
    db.flush()

    touched: list[LearnedRule] = []
    if job is None:
        db.commit()
        return fb, touched

    profile = db.query(Profile).first()
    profile_skills_lower = {s.lower() for s in (profile.skills or [])} if profile else set()
    job_skills = extract_skills_from_text(f"{job.title}\n{job.description}\n{' '.join(job.tags or [])}")
    matched_skills = [s for s in job_skills if s.lower() in profile_skills_lower]
    unmatched_skills = [s for s in job_skills if s.lower() not in profile_skills_lower]
    title_lower = (job.title or "").lower()

    positive_deltas = {
        "digest_approve": 2.0,
        "outreach_replied": 3.0,
        "interview_invited": 5.0,
        "offer_received": 7.0,
    }

    if event_type in positive_deltas:
        delta = positive_deltas[event_type]
        for sk in matched_skills[:4]:
            _upsert_rule(db, "skill", sk, delta, touched)
        for kw in SENIORITY_KEYWORDS:
            if re.search(rf"\b{kw}\b", title_lower):
                _upsert_rule(db, "title_keyword", kw, delta * 0.75, touched)
        if job.work_mode and job.work_mode != "unknown":
            _upsert_rule(db, "work_mode", job.work_mode, delta * 0.75, touched)
        if event_type in {"interview_invited", "offer_received"} and job.company:
            _upsert_rule(db, "company", normalize_company_name(job.company) or job.company, delta, touched)

    elif event_type == "digest_skip":
        reason = (reason_code or "").lower()
        if reason == "wrong_stack":
            for sk in (unmatched_skills[:4] or job_skills[:3]):
                _upsert_rule(db, "skill", sk, -4.0, touched)
        elif reason in {"too_senior", "too_junior"}:
            found_kw = False
            for kw in SENIORITY_KEYWORDS:
                if re.search(rf"\b{kw}\b", title_lower):
                    _upsert_rule(db, "title_keyword", kw, -5.0, touched)
                    found_kw = True
            if not found_kw:
                fallback_kw = "senior" if reason == "too_senior" else "junior"
                _upsert_rule(db, "title_keyword", fallback_kw, -4.0, touched)
        elif reason == "location_mismatch":
            if job.work_mode and job.work_mode != "unknown":
                _upsert_rule(db, "work_mode", job.work_mode, -4.5, touched)
            if job.location:
                _upsert_rule(db, "location", job.location.split(",")[0].strip(), -4.0, touched)
        elif reason == "company_not_interesting":
            if job.company:
                _upsert_rule(db, "company", normalize_company_name(job.company) or job.company, -6.0, touched)
        elif reason == "compensation_dealbreaker":
            if note:
                for token in [t.strip() for t in note.split(",") if len(t.strip()) >= 3][:3]:
                    _upsert_rule(db, "red_flag", token, -5.0, touched)
        else:
            for sk in unmatched_skills[:2]:
                _upsert_rule(db, "skill", sk, -2.0, touched)
            if job.work_mode and job.work_mode != "unknown":
                _upsert_rule(db, "work_mode", job.work_mode, -1.5, touched)

        # If user wrote an explicit note with "avoid X" or comma-separated terms, learn red flags cleanly
        if note and reason != "compensation_dealbreaker":
            m = re.search(r"avoid\s+([a-zA-Z0-9\+\#\.\- ]{3,30})", note, re.IGNORECASE)
            if m:
                _upsert_rule(db, "red_flag", m.group(1).strip(), -5.0, touched)

    elif event_type in {"application_rejected", "application_withdrawn"}:
        delta = -1.5 if event_type == "application_rejected" else -2.0
        for sk in unmatched_skills[:3]:
            _upsert_rule(db, "skill", sk, delta, touched)
        if reason_code == "company_not_interesting" and job.company:
            _upsert_rule(db, "company", normalize_company_name(job.company) or job.company, -4.0, touched)

    db.commit()
    return fb, touched

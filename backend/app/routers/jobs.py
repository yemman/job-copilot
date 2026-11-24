import hashlib
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import FeedbackEvent, Job, LearnedRule, Profile
from app.schemas import JobImportRequest, JobOut
from app.services.job_sources import fetch_job_details_from_url, infer_work_mode
from app.services.resume_parser import extract_skills_from_text
from app.services.scoring import score_job

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("", response_model=list[JobOut])
def list_jobs(
    status: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=300),
    db: Session = Depends(get_db),
):
    q = db.query(Job)
    if status:
        q = q.filter(Job.status == status)
    if source_type:
        q = q.filter(Job.source_type == source_type)
    if search:
        pattern = f"%{search.strip()}%"
        q = q.filter(
            or_(
                Job.title.ilike(pattern),
                Job.company.ilike(pattern),
                Job.description.ilike(pattern),
            )
        )
    return q.order_by(Job.score.desc().nullslast(), Job.ingested_at.desc()).limit(limit).all()


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/import", response_model=JobOut, status_code=201)
def import_job(payload: JobImportRequest, db: Session = Depends(get_db)):
    title = payload.title.strip()
    company = payload.company.strip()
    location = payload.location.strip()
    description = payload.description.strip()
    url = payload.url.strip()

    if url and (not title or not description):
        try:
            parsed = fetch_job_details_from_url(url)
            title = title or parsed.get("title", "")
            company = company or parsed.get("company", "")
            location = location or parsed.get("location", "")
            description = description or parsed.get("description", "")
        except Exception as exc:
            if not title:
                raise HTTPException(
                    status_code=400,
                    detail=f"Could not fetch URL automatically ({exc}). Please paste the job title and description manually.",
                )

    if not title:
        raise HTTPException(status_code=400, detail="Job title is required (or provide a fetchable job URL).")

    company = company or "Unknown Company"
    work_mode = (
        payload.work_mode
        if payload.work_mode != "unknown"
        else infer_work_mode(location, title, description)
    )
    tags = list(dict.fromkeys(payload.tags + extract_skills_from_text(f"{title}\n{description}")))[:15]

    ext_seed = url or f"{title}|{company}|{description[:120]}"
    ext_id = hashlib.sha256(ext_seed.encode("utf-8")).hexdigest()[:24]

    existing = db.query(Job).filter(Job.source_type == "manual", Job.external_id == ext_id).first()
    if existing:
        return existing

    job = Job(
        source_type="manual",
        external_id=ext_id,
        title=title[:300],
        company=company[:200],
        location=location[:200],
        work_mode=work_mode,
        url=url[:1000],
        description=description,
        tags=tags,
        salary_text=payload.salary_text[:200],
        status="new",
    )

    profile = db.query(Profile).first() or Profile()
    learned_rules = db.query(LearnedRule).all()
    recent_feedback = db.query(FeedbackEvent).order_by(FeedbackEvent.created_at.desc()).limit(10).all()
    s, bd = score_job(job, profile, learned_rules, recent_feedback, use_ai=True)
    job.score = s
    job.score_breakdown = bd

    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.post("/rescore")
def rescore_new_jobs(db: Session = Depends(get_db)):
    profile = db.query(Profile).first()
    if profile is None:
        profile = Profile()
        db.add(profile)
        db.commit()
        db.refresh(profile)

    learned_rules = db.query(LearnedRule).all()
    recent_feedback = db.query(FeedbackEvent).order_by(FeedbackEvent.created_at.desc()).limit(10).all()
    jobs = db.query(Job).filter(Job.status.in_(["new", "suggested"])).all()
    for job in jobs:
        s, bd = score_job(job, profile, learned_rules, recent_feedback, use_ai=False)
        job.score = s
        job.score_breakdown = bd
    db.commit()
    return {"rescored": len(jobs)}

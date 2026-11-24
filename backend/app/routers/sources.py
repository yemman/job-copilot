from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import JobSource
from app.schemas import JobSourceCreate, JobSourceOut, JobSourceUpdate, SyncResult
from app.services.job_sources import sync_all_enabled_sources, sync_source

router = APIRouter(prefix="/api/sources", tags=["sources"])


@router.get("", response_model=list[JobSourceOut])
def list_sources(db: Session = Depends(get_db)):
    return db.query(JobSource).order_by(JobSource.id.asc()).all()


@router.post("", response_model=JobSourceOut, status_code=201)
def create_source(payload: JobSourceCreate, db: Session = Depends(get_db)):
    src = JobSource(
        name=payload.name.strip(),
        source_type=payload.source_type,
        config=payload.config,
        enabled=payload.enabled,
    )
    db.add(src)
    db.commit()
    db.refresh(src)
    return src


@router.patch("/{source_id}", response_model=JobSourceOut)
def update_source(source_id: int, payload: JobSourceUpdate, db: Session = Depends(get_db)):
    src = db.query(JobSource).filter(JobSource.id == source_id).first()
    if not src:
        raise HTTPException(status_code=404, detail="Job source not found")
    for key, val in payload.model_dump(exclude_unset=True).items():
        setattr(src, key, val)
    db.commit()
    db.refresh(src)
    return src


@router.delete("/{source_id}")
def delete_source(source_id: int, db: Session = Depends(get_db)):
    src = db.query(JobSource).filter(JobSource.id == source_id).first()
    if not src:
        raise HTTPException(status_code=404, detail="Job source not found")
    db.delete(src)
    db.commit()
    return {"deleted": True, "id": source_id}


@router.post("/sync-all", response_model=list[SyncResult])
def sync_all_sources(db: Session = Depends(get_db)):
    return sync_all_enabled_sources(db)


@router.post("/{source_id}/sync", response_model=SyncResult)
def sync_single_source(source_id: int, db: Session = Depends(get_db)):
    src = db.query(JobSource).filter(JobSource.id == source_id).first()
    if not src:
        raise HTTPException(status_code=404, detail="Job source not found")
    return sync_source(db, src)

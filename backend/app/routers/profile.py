from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Profile
from app.schemas import ProfileOut, ProfileUpdate, ResumeUploadResult
from app.services.resume_parser import extract_resume_text, extract_skills_from_text

router = APIRouter(prefix="/api/profile", tags=["profile"])


def _get_or_create_profile(db: Session) -> Profile:
    profile = db.query(Profile).first()
    if profile is None:
        profile = Profile()
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


@router.get("", response_model=ProfileOut)
def get_profile(db: Session = Depends(get_db)):
    return _get_or_create_profile(db)


@router.put("", response_model=ProfileOut)
def update_profile(payload: ProfileUpdate, db: Session = Depends(get_db)):
    profile = _get_or_create_profile(db)
    data = payload.model_dump(exclude_unset=True)
    if "digest_days" in data and data["digest_days"] is not None:
        data["digest_days"] = [d.strip().lower() for d in data["digest_days"] if d.strip()]
    for key, val in data.items():
        setattr(profile, key, val)
    db.commit()
    db.refresh(profile)
    return profile


@router.post("/resume", response_model=ResumeUploadResult)
async def upload_resume(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    filename = file.filename or "resume.txt"
    text = extract_resume_text(filename, content)
    extracted_skills = extract_skills_from_text(text)

    profile = _get_or_create_profile(db)
    profile.resume_text = text
    profile.resume_filename = filename
    if not profile.skills and extracted_skills:
        profile.skills = extracted_skills
    db.commit()
    db.refresh(profile)
    return ResumeUploadResult(
        filename=filename,
        resume_text=text,
        extracted_skills=extracted_skills,
        profile=ProfileOut.model_validate(profile),
    )

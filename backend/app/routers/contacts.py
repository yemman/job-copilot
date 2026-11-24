from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Application, Contact
from app.schemas import (
    ApplicationConnectionsResponse,
    ContactCreate,
    ContactOut,
    ContactUpdate,
)
from app.services.outreach import (
    build_linkedin_people_search_url,
    find_matching_contacts,
    normalize_company_name,
    parse_linkedin_connections_csv,
)

router = APIRouter(tags=["contacts"])


@router.get("/api/contacts", response_model=list[ContactOut])
def list_contacts(search: str | None = Query(default=None), db: Session = Depends(get_db)):
    q = db.query(Contact)
    if search:
        pat = f"%{search.strip()}%"
        q = q.filter(
            or_(
                Contact.name.ilike(pat),
                Contact.company.ilike(pat),
                Contact.role.ilike(pat),
            )
        )
    return q.order_by(Contact.created_at.desc()).all()


@router.post("/api/contacts", response_model=ContactOut, status_code=201)
def create_contact(payload: ContactCreate, db: Session = Depends(get_db)):
    c = Contact(
        name=payload.name.strip(),
        company=payload.company.strip(),
        normalized_company=normalize_company_name(payload.company),
        role=payload.role.strip(),
        linkedin_url=payload.linkedin_url.strip(),
        email=payload.email.strip(),
        relationship=payload.relationship,
        notes=payload.notes.strip(),
        source="manual",
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.patch("/api/contacts/{contact_id}", response_model=ContactOut)
def update_contact(contact_id: int, payload: ContactUpdate, db: Session = Depends(get_db)):
    c = db.query(Contact).filter(Contact.id == contact_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Contact not found")
    data = payload.model_dump(exclude_unset=True)
    for key, val in data.items():
        setattr(c, key, val)
    if "company" in data:
        c.normalized_company = normalize_company_name(c.company)
    db.commit()
    db.refresh(c)
    return c


@router.delete("/api/contacts/{contact_id}")
def delete_contact(contact_id: int, db: Session = Depends(get_db)):
    c = db.query(Contact).filter(Contact.id == contact_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Contact not found")
    db.delete(c)
    db.commit()
    return {"deleted": True, "id": contact_id}


@router.post("/api/contacts/import-linkedin-csv")
async def import_linkedin_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    raw = await file.read()
    rows = parse_linkedin_connections_csv(raw)
    if not rows:
        raise HTTPException(
            status_code=400,
            detail="Could not find LinkedIn Connections header row (expected First Name, Last Name, Company).",
        )

    inserted = 0
    skipped = 0
    for row in rows:
        name = row["name"]
        company = row["company"]
        norm = normalize_company_name(company)
        existing = (
            db.query(Contact)
            .filter(Contact.name == name, Contact.normalized_company == norm)
            .first()
        )
        if existing:
            skipped += 1
            continue
        db.add(
            Contact(
                name=name,
                company=company,
                normalized_company=norm,
                role=row["role"],
                linkedin_url=row["linkedin_url"],
                email=row["email"],
                relationship="1st_degree",
                notes=f"Connected on {row['connected_on']}" if row["connected_on"] else "",
                source="linkedin_csv",
            )
        )
        inserted += 1

    db.commit()
    return {"parsed": len(rows), "inserted": inserted, "skipped_duplicates": skipped}


@router.get("/api/applications/{application_id}/connections", response_model=ApplicationConnectionsResponse)
def get_application_connections(application_id: int, db: Session = Depends(get_db)):
    app_obj = db.query(Application).filter(Application.id == application_id).first()
    if not app_obj:
        raise HTTPException(status_code=404, detail="Application not found")
    company = app_obj.job.company if app_obj.job else ""
    role_hint = ""
    matches = find_matching_contacts(db, company)
    return ApplicationConnectionsResponse(
        application_id=app_obj.id,
        company=company,
        normalized_company=normalize_company_name(company),
        linkedin_search_url=build_linkedin_people_search_url(company, role_hint),
        matched_contacts=[ContactOut.model_validate(c) for c in matches],
    )

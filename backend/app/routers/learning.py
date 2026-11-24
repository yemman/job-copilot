from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import FeedbackEvent, LearnedRule
from app.schemas import (
    FeedbackEventOut,
    LearnedRuleCreate,
    LearnedRuleOut,
    LearnedRuleUpdate,
)

router = APIRouter(prefix="/api/learning", tags=["learning"])


@router.get("/rules", response_model=list[LearnedRuleOut])
def list_rules(db: Session = Depends(get_db)):
    return db.query(LearnedRule).order_by(LearnedRule.weight.desc()).all()


@router.post("/rules", response_model=LearnedRuleOut, status_code=201)
def create_rule(payload: LearnedRuleCreate, db: Session = Depends(get_db)):
    term = payload.term.strip()
    if not term:
        raise HTTPException(status_code=400, detail="Term cannot be empty")
    existing = (
        db.query(LearnedRule)
        .filter(LearnedRule.category == payload.category, LearnedRule.term == term)
        .first()
    )
    if existing:
        existing.weight = payload.weight
        existing.locked = payload.locked
        existing.enabled = payload.enabled
        existing.source = "manual"
        db.commit()
        db.refresh(existing)
        return existing

    rule = LearnedRule(
        category=payload.category,
        term=term,
        weight=payload.weight,
        evidence_count=1,
        source="manual",
        locked=payload.locked,
        enabled=payload.enabled,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.patch("/rules/{rule_id}", response_model=LearnedRuleOut)
def update_rule(rule_id: int, payload: LearnedRuleUpdate, db: Session = Depends(get_db)):
    rule = db.query(LearnedRule).filter(LearnedRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Learned rule not found")
    for key, val in payload.model_dump(exclude_unset=True).items():
        setattr(rule, key, val)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.query(LearnedRule).filter(LearnedRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Learned rule not found")
    db.delete(rule)
    db.commit()
    return {"deleted": True, "id": rule_id}


@router.get("/feedback", response_model=list[FeedbackEventOut])
def list_feedback(db: Session = Depends(get_db)):
    return db.query(FeedbackEvent).order_by(FeedbackEvent.created_at.desc()).limit(50).all()

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Profile ---
class ProfileOut(ORMModel):
    id: int
    full_name: str
    headline: str
    resume_text: str
    resume_filename: str
    skills: list[str]
    target_roles: list[str]
    preferred_locations: list[str]
    work_mode: str
    experience_years: int
    dealbreakers: list[str]
    notes_for_ai: str
    daily_pick_count: int
    digest_days: list[str]
    digest_hour: int
    timezone: str
    updated_at: datetime | None = None


class ProfileUpdate(BaseModel):
    full_name: str | None = None
    headline: str | None = None
    resume_text: str | None = None
    resume_filename: str | None = None
    skills: list[str] | None = None
    target_roles: list[str] | None = None
    preferred_locations: list[str] | None = None
    work_mode: Literal["remote", "hybrid", "onsite", "any"] | None = None
    experience_years: int | None = Field(default=None, ge=0, le=60)
    dealbreakers: list[str] | None = None
    notes_for_ai: str | None = None
    daily_pick_count: int | None = Field(default=None, ge=3, le=5)
    digest_days: list[str] | None = None
    digest_hour: int | None = Field(default=None, ge=0, le=23)
    timezone: str | None = None


class ResumeUploadResult(BaseModel):
    filename: str
    resume_text: str
    extracted_skills: list[str]
    profile: ProfileOut


# --- Job Sources ---
class JobSourceCreate(BaseModel):
    name: str
    source_type: Literal["greenhouse", "lever", "ashby", "remotive", "arbeitnow"]
    config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class JobSourceUpdate(BaseModel):
    name: str | None = None
    config: dict[str, Any] | None = None
    enabled: bool | None = None


class JobSourceOut(ORMModel):
    id: int
    name: str
    source_type: str
    config: dict[str, Any]
    enabled: bool
    last_synced_at: datetime | None = None
    last_sync_status: str
    last_sync_count: int
    created_at: datetime


class SyncResult(BaseModel):
    source_id: int
    source_name: str
    status: str
    fetched_count: int
    inserted_count: int
    error: str | None = None


# --- Jobs ---
class JobOut(ORMModel):
    id: int
    source_id: int | None = None
    source_type: str
    external_id: str | None = None
    title: str
    company: str
    location: str
    work_mode: str
    url: str
    description: str
    tags: list[str]
    salary_text: str
    posted_at: str
    ingested_at: datetime
    score: float | None = None
    score_breakdown: dict[str, Any]
    status: str


class JobImportRequest(BaseModel):
    url: str = ""
    title: str = ""
    company: str = ""
    location: str = ""
    work_mode: Literal["remote", "hybrid", "onsite", "unknown"] = "unknown"
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    salary_text: str = ""


# --- Daily Digest ---
class DailyDigestItemOut(ORMModel):
    id: int
    digest_id: int
    job_id: int
    rank: int
    score_snapshot: float
    rationale_snapshot: str
    decision: str
    decided_at: datetime | None = None
    job: JobOut


class DailyDigestOut(ORMModel):
    id: int
    digest_date: str
    day_of_week: str
    scheduled: bool
    created_at: datetime
    notes: str
    items: list[DailyDigestItemOut]


class DigestTodayResponse(BaseModel):
    today_date: str
    day_of_week: str
    is_scheduled_day: bool
    digest_days: list[str]
    next_digest_day: str
    digest: DailyDigestOut | None = None


class DigestGenerateRequest(BaseModel):
    force: bool = False
    sync_sources: bool = False


class DigestDecisionRequest(BaseModel):
    decision: Literal["approved", "skipped"]
    reason_code: str | None = None
    note: str | None = None


# --- Contacts & Outreach ---
class ContactCreate(BaseModel):
    name: str
    company: str = ""
    role: str = ""
    linkedin_url: str = ""
    email: str = ""
    relationship: Literal[
        "1st_degree", "former_colleague", "alumni", "recruiter", "cold_target"
    ] = "1st_degree"
    notes: str = ""


class ContactUpdate(BaseModel):
    name: str | None = None
    company: str | None = None
    role: str | None = None
    linkedin_url: str | None = None
    email: str | None = None
    relationship: Literal[
        "1st_degree", "former_colleague", "alumni", "recruiter", "cold_target"
    ] | None = None
    notes: str | None = None


class ContactOut(ORMModel):
    id: int
    name: str
    company: str
    normalized_company: str
    role: str
    linkedin_url: str
    email: str
    relationship: str
    notes: str
    source: str
    created_at: datetime


class OutreachDraftRequest(BaseModel):
    contact_id: int | None = None
    contact_name: str = ""
    channel: Literal["linkedin_connect_note", "linkedin_dm", "email"] = "linkedin_connect_note"


class OutreachUpdateRequest(BaseModel):
    subject: str | None = None
    body: str | None = None
    channel: Literal["linkedin_connect_note", "linkedin_dm", "email"] | None = None


class OutreachReplyRequest(BaseModel):
    replied: bool = True
    reply_notes: str = ""
    advance_to_ready_to_apply: bool = False


class OutreachMessageOut(ORMModel):
    id: int
    application_id: int
    contact_id: int | None = None
    contact_name_snapshot: str
    channel: str
    subject: str
    body: str
    status: str
    approved_at: datetime | None = None
    sent_at: datetime | None = None
    follow_up_at: datetime | None = None
    reply_notes: str
    created_at: datetime
    updated_at: datetime


# --- Pipeline & Applications ---
class ActivityLogOut(ORMModel):
    id: int
    application_id: int | None = None
    action: str
    details: str
    created_at: datetime


class ApplicationOut(ORMModel):
    id: int
    job_id: int
    stage: str
    connection_override_reason: str | None = None
    applied_at: datetime | None = None
    next_step: str
    next_step_at: datetime | None = None
    outcome_reason: str
    notes: str
    created_at: datetime
    updated_at: datetime
    job: JobOut
    outreach_messages: list[OutreachMessageOut] = Field(default_factory=list)
    activity_logs: list[ActivityLogOut] = Field(default_factory=list)
    matched_contacts_count: int = 0


class ApplicationUpdate(BaseModel):
    notes: str | None = None
    next_step: str | None = None
    next_step_at: datetime | None = None


class ApplicationTransitionRequest(BaseModel):
    stage: Literal[
        "connection_search",
        "outreach_drafted",
        "outreach_sent",
        "ready_to_apply",
        "applied",
        "interviewing",
        "offer",
        "rejected",
        "withdrawn",
    ]
    connection_override_reason: str | None = None
    outcome_reason: str | None = None
    note: str | None = None


class ApplicationConnectionsResponse(BaseModel):
    application_id: int
    company: str
    normalized_company: str
    linkedin_search_url: str
    matched_contacts: list[ContactOut]


# --- Learning ---
class LearnedRuleCreate(BaseModel):
    category: Literal["skill", "title_keyword", "company", "work_mode", "location", "red_flag"]
    term: str
    weight: float = Field(ge=-20.0, le=20.0)
    locked: bool = True
    enabled: bool = True


class LearnedRuleUpdate(BaseModel):
    weight: float | None = Field(default=None, ge=-20.0, le=20.0)
    locked: bool | None = None
    enabled: bool | None = None


class LearnedRuleOut(ORMModel):
    id: int
    category: str
    term: str
    weight: float
    evidence_count: int
    source: str
    locked: bool
    enabled: bool
    updated_at: datetime


class FeedbackEventOut(ORMModel):
    id: int
    job_id: int | None = None
    application_id: int | None = None
    event_type: str
    reason_code: str | None = None
    note: str | None = None
    job_snapshot: dict[str, Any]
    created_at: datetime

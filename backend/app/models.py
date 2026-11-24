from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200), default="Job Seeker")
    headline: Mapped[str] = mapped_column(String(300), default="")
    resume_text: Mapped[str] = mapped_column(Text, default="")
    resume_filename: Mapped[str] = mapped_column(String(255), default="")
    skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    target_roles: Mapped[list[str]] = mapped_column(JSON, default=list)
    preferred_locations: Mapped[list[str]] = mapped_column(JSON, default=list)
    work_mode: Mapped[str] = mapped_column(String(32), default="any")  # remote|hybrid|onsite|any
    experience_years: Mapped[int] = mapped_column(Integer, default=3)
    dealbreakers: Mapped[list[str]] = mapped_column(JSON, default=list)
    notes_for_ai: Mapped[str] = mapped_column(Text, default="")
    daily_pick_count: Mapped[int] = mapped_column(Integer, default=4)  # 3-5
    digest_days: Mapped[list[str]] = mapped_column(
        JSON, default=lambda: ["sun", "mon", "tue", "wed"]
    )
    digest_hour: Mapped[int] = mapped_column(Integer, default=9)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Jerusalem")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class JobSource(Base):
    __tablename__ = "job_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    source_type: Mapped[str] = mapped_column(String(50))  # greenhouse|lever|ashby|remotive|arbeitnow
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_status: Mapped[str] = mapped_column(String(255), default="")
    last_sync_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="source")


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("source_type", "external_id", name="uq_job_source_external"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("job_sources.id", ondelete="SET NULL"), nullable=True
    )
    source_type: Mapped[str] = mapped_column(String(50), default="manual")
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(String(300), index=True)
    company: Mapped[str] = mapped_column(String(200), index=True)
    location: Mapped[str] = mapped_column(String(200), default="")
    work_mode: Mapped[str] = mapped_column(String(32), default="unknown")  # remote|hybrid|onsite|unknown
    url: Mapped[str] = mapped_column(String(1000), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    salary_text: Mapped[str] = mapped_column(String(200), default="")
    posted_at: Mapped[str] = mapped_column(String(100), default="")
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    score: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    score_breakdown: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(
        String(32), default="new", index=True
    )  # new|suggested|approved|skipped|archived

    source: Mapped["JobSource | None"] = relationship("JobSource", back_populates="jobs")
    application: Mapped["Application | None"] = relationship(
        "Application", back_populates="job", uselist=False
    )


class DailyDigest(Base):
    __tablename__ = "daily_digests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    digest_date: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    day_of_week: Mapped[str] = mapped_column(String(16))
    scheduled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    notes: Mapped[str] = mapped_column(Text, default="")

    items: Mapped[list["DailyDigestItem"]] = relationship(
        "DailyDigestItem", back_populates="digest", cascade="all, delete-orphan", order_by="DailyDigestItem.rank"
    )


class DailyDigestItem(Base):
    __tablename__ = "daily_digest_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    digest_id: Mapped[int] = mapped_column(Integer, ForeignKey("daily_digests.id", ondelete="CASCADE"))
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"))
    rank: Mapped[int] = mapped_column(Integer, default=1)
    score_snapshot: Mapped[float] = mapped_column(Float, default=0.0)
    rationale_snapshot: Mapped[str] = mapped_column(Text, default="")
    decision: Mapped[str] = mapped_column(String(32), default="pending")  # pending|approved|skipped
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    digest: Mapped["DailyDigest"] = relationship("DailyDigest", back_populates="items")
    job: Mapped["Job"] = relationship("Job")


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), unique=True)
    stage: Mapped[str] = mapped_column(
        String(40), default="connection_search", index=True
    )  # connection_search|outreach_drafted|outreach_sent|ready_to_apply|applied|interviewing|offer|rejected|withdrawn
    connection_override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_step: Mapped[str] = mapped_column(String(300), default="")
    next_step_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome_reason: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    job: Mapped["Job"] = relationship("Job", back_populates="application")
    outreach_messages: Mapped[list["OutreachMessage"]] = relationship(
        "OutreachMessage", back_populates="application", cascade="all, delete-orphan", order_by="OutreachMessage.created_at.desc()"
    )
    activity_logs: Mapped[list["ActivityLog"]] = relationship(
        "ActivityLog", back_populates="application", cascade="all, delete-orphan", order_by="ActivityLog.created_at.desc()"
    )


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    company: Mapped[str] = mapped_column(String(200), default="")
    normalized_company: Mapped[str] = mapped_column(String(200), default="", index=True)
    role: Mapped[str] = mapped_column(String(200), default="")
    linkedin_url: Mapped[str] = mapped_column(String(500), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    relationship: Mapped[str] = mapped_column(
        String(50), default="1st_degree"
    )  # 1st_degree|former_colleague|alumni|recruiter|cold_target
    notes: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(32), default="manual")  # manual|linkedin_csv
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OutreachMessage(Base):
    __tablename__ = "outreach_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    contact_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True
    )
    contact_name_snapshot: Mapped[str] = mapped_column(String(200), default="")
    channel: Mapped[str] = mapped_column(
        String(40), default="linkedin_connect_note"
    )  # linkedin_connect_note|linkedin_dm|email
    subject: Mapped[str] = mapped_column(String(300), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(
        String(32), default="draft"
    )  # draft|approved|sent|replied|no_response
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    follow_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reply_notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    application: Mapped["Application"] = relationship("Application", back_populates="outreach_messages")
    contact: Mapped["Contact | None"] = relationship("Contact")


class FeedbackEvent(Base):
    __tablename__ = "feedback_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True
    )
    application_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("applications.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(
        String(50), index=True
    )  # digest_approve|digest_skip|outreach_replied|interview_invited|offer_received|application_rejected|application_withdrawn
    reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    job_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LearnedRule(Base):
    __tablename__ = "learned_rules"
    __table_args__ = (
        UniqueConstraint("category", "term", name="uq_learned_rule_cat_term"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    category: Mapped[str] = mapped_column(
        String(40), index=True
    )  # skill|title_keyword|company|work_mode|location|red_flag
    term: Mapped[str] = mapped_column(String(150), index=True)
    weight: Mapped[float] = mapped_column(Float, default=0.0)
    evidence_count: Mapped[int] = mapped_column(Integer, default=1)
    source: Mapped[str] = mapped_column(String(32), default="learned")  # learned|manual
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(100))
    details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    application: Mapped["Application | None"] = relationship("Application", back_populates="activity_logs")

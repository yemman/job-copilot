from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.models import Job
from app.services.digest import generate_daily_digest


def _add_sample_jobs(db_session, count: int = 7) -> None:
    for i in range(count):
        db_session.add(
            Job(
                source_type="demo",
                external_id=f"d-{i}",
                title=f"Backend Engineer {i}",
                company=f"Company{i}",
                location="Remote",
                work_mode="remote",
                description="Python FastAPI React PostgreSQL Docker",
                tags=["Python", "FastAPI"],
                status="new",
            )
        )
    db_session.commit()


def test_sun_wed_schedule_gating_and_no_duplicates(db_session):
    _add_sample_jobs(db_session, 7)

    # 2026-11-26 is a Thursday (off-schedule)
    thursday = datetime(2026, 11, 26, 9, 0, tzinfo=ZoneInfo("Asia/Jerusalem"))
    skipped_res = generate_daily_digest(db_session, force=False, now_override=thursday)
    assert skipped_res["skipped"] is True
    assert skipped_res["digest"] is None

    # 2026-11-24 is a Tuesday (active Sun-Wed)
    tuesday = datetime(2026, 11, 24, 9, 0, tzinfo=ZoneInfo("Asia/Jerusalem"))
    ok_res = generate_daily_digest(db_session, force=False, now_override=tuesday)
    assert ok_res["skipped"] is False
    digest1 = ok_res["digest"]
    assert digest1 is not None
    assert 3 <= len(digest1.items) <= 5
    first_job_ids = {item.job_id for item in digest1.items}

    # Force run on Thursday picks remaining unseen jobs and never repeats Tuesday's picks
    thursday_force = generate_daily_digest(db_session, force=True, now_override=thursday)
    digest2 = thursday_force["digest"]
    assert digest2 is not None
    second_job_ids = {item.job_id for item in digest2.items}
    assert len(second_job_ids) > 0
    assert first_job_ids.isdisjoint(second_job_ids)


def test_cron_secret_enforcement(client, db_session, monkeypatch):
    _add_sample_jobs(db_session, 5)
    monkeypatch.setenv("CRON_SECRET", "super-secret-token")
    assert get_settings().cron_secret == "super-secret-token"

    unauthorized = client.post("/api/cron/daily-digest")
    assert unauthorized.status_code == 401

    wrong = client.post("/api/cron/daily-digest", headers={"X-Cron-Secret": "wrong"})
    assert wrong.status_code == 401

    ok = client.post("/api/cron/daily-digest", headers={"X-Cron-Secret": "super-secret-token"})
    assert ok.status_code == 200

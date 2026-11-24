from contextlib import asynccontextmanager
import logging
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal, get_db, init_db
from app.routers import contacts, digest, jobs, learning, outreach, pipeline, profile, sources
from app.services.digest import generate_daily_digest
from app.services.gemini_client import is_gemini_enabled
from app.services.seed import load_demo_workspace, seed_default_sources_if_empty

logger = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None


def _scheduled_digest_job() -> None:
    db = SessionLocal()
    try:
        res = generate_daily_digest(db, force=False, sync_sources=True)
        logger.info("Scheduled Sun-Wed digest run: %s", res.get("reason"))
    except Exception as exc:
        logger.exception("Scheduled digest failed: %s", exc)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheduler
    init_db()
    db = SessionLocal()
    try:
        seed_default_sources_if_empty(db)
    finally:
        db.close()

    cfg = get_settings()
    if cfg.enable_scheduler:
        _scheduler = BackgroundScheduler(timezone=cfg.digest_timezone)
        _scheduler.add_job(
            _scheduled_digest_job,
            CronTrigger(
                day_of_week="sun,mon,tue,wed",
                hour=cfg.digest_hour,
                minute=0,
                timezone=cfg.digest_timezone,
            ),
            id="sun_wed_daily_digest",
            replace_existing=True,
        )
        _scheduler.start()
        logger.info(
            "APScheduler started: Sun-Wed at %02d:00 (%s)",
            cfg.digest_hour,
            cfg.digest_timezone,
        )

    yield

    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)


app = FastAPI(title="Job Copilot API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(profile.router)
app.include_router(sources.router)
app.include_router(jobs.router)
app.include_router(digest.router)
app.include_router(pipeline.router)
app.include_router(contacts.router)
app.include_router(outreach.router)
app.include_router(learning.router)


@app.get("/api/health")
def health_check():
    cfg = get_settings()
    return {
        "status": "ok",
        "ai_mode": "gemini" if is_gemini_enabled() else "heuristic",
        "gemini_model": cfg.gemini_model,
        "scheduler_running": bool(_scheduler and _scheduler.running),
    }


@app.post("/api/demo/seed")
def seed_demo(db: Session = Depends(get_db)):
    return load_demo_workspace(db)


# Serve built React frontend in production / Docker when frontend/dist exists
_dist_dir: Path = get_settings().frontend_dist_dir
if _dist_dir.exists() and (_dist_dir / "index.html").exists():
    assets_dir = _dist_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        if full_path.startswith("api/"):
            return {"detail": "Not found"}
        candidate = _dist_dir / full_path
        if full_path and candidate.exists() and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(_dist_dir / "index.html"))

from dataclasses import dataclass
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / "backend" / ".env")


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'job_copilot.db'}")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "").strip()
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
    cron_secret: str = os.getenv("CRON_SECRET", "").strip()
    digest_timezone: str = os.getenv("DIGEST_TIMEZONE", "Asia/Jerusalem").strip() or "Asia/Jerusalem"
    digest_hour: int = int(os.getenv("DIGEST_HOUR", "9"))
    enable_scheduler: bool = _parse_bool(os.getenv("ENABLE_SCHEDULER"), True)
    frontend_dist_dir: Path = Path(
        os.getenv("FRONTEND_DIST_DIR", str(BASE_DIR / "frontend" / "dist"))
    )


def get_settings() -> Settings:
    """Return fresh settings reading current environment variables."""
    return Settings(
        database_url=os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'job_copilot.db'}"),
        gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash",
        cron_secret=os.getenv("CRON_SECRET", "").strip(),
        digest_timezone=os.getenv("DIGEST_TIMEZONE", "Asia/Jerusalem").strip() or "Asia/Jerusalem",
        digest_hour=int(os.getenv("DIGEST_HOUR", "9")),
        enable_scheduler=_parse_bool(os.getenv("ENABLE_SCHEDULER"), True),
        frontend_dist_dir=Path(
            os.getenv("FRONTEND_DIST_DIR", str(BASE_DIR / "frontend" / "dist"))
        ),
    )


settings = get_settings()

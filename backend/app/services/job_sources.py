from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import re
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup
import httpx
from sqlalchemy.orm import Session

from app.models import Job, JobSource
from app.services.resume_parser import extract_skills_from_text

USER_AGENT = "JobCopilot/1.0 (personal-job-assistant)"


@dataclass
class NormalizedJob:
    external_id: str | None
    source_type: str
    title: str
    company: str
    location: str = ""
    work_mode: str = "unknown"
    url: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    salary_text: str = ""
    posted_at: str = ""


def strip_html(raw: str) -> str:
    if not raw:
        return ""
    if "<" not in raw:
        return re.sub(r"\s+", " ", raw).strip()
    soup = BeautifulSoup(raw, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def infer_work_mode(location: str, title: str = "", description: str = "", explicit_remote: bool | None = None) -> str:
    if explicit_remote is True:
        return "remote"
    blob = f"{location} {title} {description[:600]}".lower()
    if "hybrid" in blob:
        return "hybrid"
    if any(k in blob for k in ("remote", "work from home", "wfh", "anywhere", "distributed")):
        return "remote"
    if any(k in blob for k in ("on-site", "onsite", "in-office", "in person")):
        return "onsite"
    return "unknown"


def parse_greenhouse_payload(data: dict[str, Any], company_name: str = "") -> list[NormalizedJob]:
    jobs: list[NormalizedJob] = []
    for item in data.get("jobs", []):
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        loc = ((item.get("location") or {}).get("name") or "").strip()
        desc = strip_html(str(item.get("content") or ""))
        comp = company_name or str(item.get("company_name") or "Greenhouse Board").strip()
        depts = [d.get("name", "") for d in (item.get("departments") or []) if d.get("name")]
        tags = list(dict.fromkeys(depts + extract_skills_from_text(f"{title}\n{desc}")))[:15]
        jobs.append(
            NormalizedJob(
                external_id=str(item.get("id") or item.get("absolute_url") or title),
                source_type="greenhouse",
                title=title,
                company=comp,
                location=loc,
                work_mode=infer_work_mode(loc, title, desc),
                url=str(item.get("absolute_url") or ""),
                description=desc,
                tags=tags,
                posted_at=str(item.get("updated_at") or ""),
            )
        )
    return jobs


def parse_lever_payload(data: list[dict[str, Any]], company_name: str = "") -> list[NormalizedJob]:
    jobs: list[NormalizedJob] = []
    for item in data:
        title = str(item.get("text") or "").strip()
        if not title:
            continue
        cats = item.get("categories") or {}
        loc = str(cats.get("location") or "").strip()
        workplace = str(item.get("workplaceType") or "").lower()
        desc = strip_html(str(item.get("descriptionPlain") or item.get("description") or ""))
        lists_text = " ".join(
            strip_html(str(lst.get("content") or "")) for lst in (item.get("lists") or [])
        )
        full_desc = f"{desc}\n{lists_text}".strip()
        comp = company_name or "Lever Board"
        work_mode = (
            workplace
            if workplace in {"remote", "hybrid", "onsite"}
            else infer_work_mode(loc, title, full_desc)
        )
        raw_tags = [str(cats.get("team") or ""), str(cats.get("department") or "")]
        tags = list(
            dict.fromkeys([t for t in raw_tags if t] + extract_skills_from_text(f"{title}\n{full_desc}"))
        )[:15]
        jobs.append(
            NormalizedJob(
                external_id=str(item.get("id") or item.get("hostedUrl") or title),
                source_type="lever",
                title=title,
                company=comp,
                location=loc,
                work_mode=work_mode,
                url=str(item.get("hostedUrl") or item.get("applyUrl") or ""),
                description=full_desc,
                tags=tags,
                posted_at=str(item.get("createdAt") or ""),
            )
        )
    return jobs


def parse_ashby_payload(data: dict[str, Any], company_name: str = "") -> list[NormalizedJob]:
    jobs: list[NormalizedJob] = []
    for item in data.get("jobs", []):
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        loc = str(item.get("location") or "").strip()
        desc = strip_html(str(item.get("descriptionPlain") or item.get("descriptionHtml") or ""))
        comp = company_name or str(data.get("organizationName") or "Ashby Board").strip()
        is_remote = item.get("isRemote")
        work_mode = infer_work_mode(loc, title, desc, explicit_remote=is_remote if isinstance(is_remote, bool) else None)
        dept = str(item.get("department") or "").strip()
        tags = list(
            dict.fromkeys(([dept] if dept else []) + extract_skills_from_text(f"{title}\n{desc}"))
        )[:15]
        jobs.append(
            NormalizedJob(
                external_id=str(item.get("id") or item.get("jobUrl") or title),
                source_type="ashby",
                title=title,
                company=comp,
                location=loc,
                work_mode=work_mode,
                url=str(item.get("jobUrl") or item.get("applyUrl") or ""),
                description=desc,
                tags=tags,
                posted_at=str(item.get("publishedAt") or ""),
            )
        )
    return jobs


def parse_remotive_payload(data: dict[str, Any]) -> list[NormalizedJob]:
    jobs: list[NormalizedJob] = []
    for item in data.get("jobs", []):
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        desc = strip_html(str(item.get("description") or ""))
        loc = str(item.get("candidate_required_location") or "Remote").strip()
        raw_tags = [str(t) for t in (item.get("tags") or []) if t]
        tags = list(dict.fromkeys(raw_tags + extract_skills_from_text(f"{title}\n{desc}")))[:15]
        jobs.append(
            NormalizedJob(
                external_id=str(item.get("id") or item.get("url") or title),
                source_type="remotive",
                title=title,
                company=str(item.get("company_name") or "Unknown").strip(),
                location=loc,
                work_mode="remote",
                url=str(item.get("url") or ""),
                description=desc,
                tags=tags,
                salary_text=str(item.get("salary") or "").strip(),
                posted_at=str(item.get("publication_date") or ""),
            )
        )
    return jobs


def parse_arbeitnow_payload(data: dict[str, Any]) -> list[NormalizedJob]:
    jobs: list[NormalizedJob] = []
    for item in data.get("data", []):
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        desc = strip_html(str(item.get("description") or ""))
        loc = str(item.get("location") or "").strip()
        is_remote = bool(item.get("remote"))
        raw_tags = [str(t) for t in (item.get("tags") or []) if t]
        tags = list(dict.fromkeys(raw_tags + extract_skills_from_text(f"{title}\n{desc}")))[:15]
        jobs.append(
            NormalizedJob(
                external_id=str(item.get("slug") or item.get("url") or title),
                source_type="arbeitnow",
                title=title,
                company=str(item.get("company_name") or "Unknown").strip(),
                location=loc,
                work_mode=infer_work_mode(loc, title, desc, explicit_remote=is_remote),
                url=str(item.get("url") or ""),
                description=desc,
                tags=tags,
                posted_at=str(item.get("created_at") or ""),
            )
        )
    return jobs


def fetch_jobs_from_source(source: JobSource) -> list[NormalizedJob]:
    cfg = source.config or {}
    stype = source.source_type
    limit = int(cfg.get("limit", 40))

    with httpx.Client(timeout=20.0, headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
        if stype == "greenhouse":
            token = str(cfg.get("board_token") or "").strip()
            if not token:
                raise ValueError("Greenhouse source requires config.board_token")
            resp = client.get(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true")
            resp.raise_for_status()
            return parse_greenhouse_payload(resp.json(), company_name=str(cfg.get("company_name") or source.name))[:limit]

        if stype == "lever":
            slug = str(cfg.get("company_slug") or cfg.get("board_token") or "").strip()
            if not slug:
                raise ValueError("Lever source requires config.company_slug")
            resp = client.get(f"https://api.lever.co/v0/postings/{slug}?mode=json")
            resp.raise_for_status()
            return parse_lever_payload(resp.json(), company_name=str(cfg.get("company_name") or source.name))[:limit]

        if stype == "ashby":
            slug = str(cfg.get("company_slug") or cfg.get("board_token") or "").strip()
            if not slug:
                raise ValueError("Ashby source requires config.company_slug")
            resp = client.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
            resp.raise_for_status()
            return parse_ashby_payload(resp.json(), company_name=str(cfg.get("company_name") or source.name))[:limit]

        if stype == "remotive":
            params: dict[str, Any] = {"limit": limit}
            if cfg.get("search"):
                params["search"] = str(cfg["search"])
            if cfg.get("category"):
                params["category"] = str(cfg["category"])
            resp = client.get("https://remotive.com/api/remote-jobs", params=params)
            resp.raise_for_status()
            return parse_remotive_payload(resp.json())[:limit]

        if stype == "arbeitnow":
            resp = client.get("https://www.arbeitnow.com/api/job-board-api")
            resp.raise_for_status()
            jobs = parse_arbeitnow_payload(resp.json())
            search_term = str(cfg.get("search") or "").strip().lower()
            if search_term:
                jobs = [
                    j for j in jobs
                    if search_term in j.title.lower() or search_term in j.description.lower()
                ]
            return jobs[:limit]

        raise ValueError(f"Unsupported source_type: {stype}")


def upsert_normalized_jobs(
    db: Session, normalized_jobs: list[NormalizedJob], source_id: int | None = None
) -> int:
    inserted = 0
    for nj in normalized_jobs:
        if nj.external_id:
            existing = (
                db.query(Job)
                .filter(Job.source_type == nj.source_type, Job.external_id == nj.external_id)
                .first()
            )
            if existing:
                continue
        elif nj.url:
            existing = db.query(Job).filter(Job.url == nj.url).first()
            if existing:
                continue

        job = Job(
            source_id=source_id,
            source_type=nj.source_type,
            external_id=nj.external_id,
            title=nj.title[:300],
            company=nj.company[:200],
            location=nj.location[:200],
            work_mode=nj.work_mode,
            url=nj.url[:1000],
            description=nj.description,
            tags=nj.tags,
            salary_text=nj.salary_text[:200],
            posted_at=nj.posted_at[:100],
            status="new",
        )
        db.add(job)
        inserted += 1
    db.commit()
    return inserted


def sync_source(db: Session, source: JobSource) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    try:
        fetched = fetch_jobs_from_source(source)
        inserted = upsert_normalized_jobs(db, fetched, source_id=source.id)
        source.last_synced_at = now
        source.last_sync_status = "ok"
        source.last_sync_count = inserted
        db.commit()
        return {
            "source_id": source.id,
            "source_name": source.name,
            "status": "ok",
            "fetched_count": len(fetched),
            "inserted_count": inserted,
            "error": None,
        }
    except Exception as exc:
        source.last_synced_at = now
        source.last_sync_status = f"error: {str(exc)[:180]}"
        source.last_sync_count = 0
        db.commit()
        return {
            "source_id": source.id,
            "source_name": source.name,
            "status": "error",
            "fetched_count": 0,
            "inserted_count": 0,
            "error": str(exc),
        }


def sync_all_enabled_sources(db: Session) -> list[dict[str, Any]]:
    sources = db.query(JobSource).filter(JobSource.enabled.is_(True)).all()
    return [sync_source(db, src) for src in sources]


def parse_job_html(html: str, url: str = "") -> dict[str, str]:
    """Parse JobPosting JSON-LD or fallback meta/title tags from a job page."""
    soup = BeautifulSoup(html, "html.parser")
    title = ""
    company = ""
    location = ""
    description = ""

    # Check JSON-LD JobPosting schema
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            payload = json.loads(script.string or "{}")
        except json.JSONDecodeError:
            continue
        candidates = payload if isinstance(payload, list) else [payload]
        for node in candidates:
            if not isinstance(node, dict):
                continue
            if node.get("@type") == "JobPosting":
                title = str(node.get("title") or "").strip()
                org = node.get("hiringOrganization") or {}
                if isinstance(org, dict):
                    company = str(org.get("name") or "").strip()
                loc = node.get("jobLocation") or {}
                if isinstance(loc, list) and loc:
                    loc = loc[0]
                if isinstance(loc, dict):
                    addr = loc.get("address") or {}
                    if isinstance(addr, dict):
                        parts = [addr.get("addressLocality"), addr.get("addressCountry")]
                        location = ", ".join(str(p) for p in parts if p)
                description = strip_html(str(node.get("description") or ""))
                break
        if title:
            break

    if not title:
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = str(og_title["content"]).strip()
        elif soup.title and soup.title.string:
            title = soup.title.string.strip()

    if not company:
        og_site = soup.find("meta", property="og:site_name")
        if og_site and og_site.get("content"):
            company = str(og_site["content"]).strip()
        elif url:
            host = urlparse(url).netloc.replace("www.", "")
            company = host.split(".")[0].title() if host else ""

    if not description:
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        description = re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()[:6000]

    return {
        "title": title,
        "company": company,
        "location": location,
        "description": description,
    }


def fetch_job_details_from_url(url: str) -> dict[str, str]:
    with httpx.Client(timeout=15.0, headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return parse_job_html(resp.text, url=url)

from app.services.job_sources import (
    parse_arbeitnow_payload,
    parse_ashby_payload,
    parse_greenhouse_payload,
    parse_lever_payload,
    parse_remotive_payload,
    upsert_normalized_jobs,
)
from app.services.resume_parser import extract_resume_text, extract_skills_from_text


def test_resume_text_and_skill_extraction(client):
    content = b"Senior Backend Engineer skilled in Python, FastAPI, PostgreSQL, Docker, and GCP."
    text = extract_resume_text("resume.txt", content)
    assert "FastAPI" in text
    skills = extract_skills_from_text(text)
    assert "Python" in skills
    assert "FastAPI" in skills
    assert "PostgreSQL" in skills
    assert "GCP" in skills

    resp = client.post(
        "/api/profile/resume",
        files={"file": ("my_cv.md", content, "text/markdown")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["filename"] == "my_cv.md"
    assert "FastAPI" in data["extracted_skills"]


def test_ats_payload_parsers_and_deduplication(db_session):
    gh = parse_greenhouse_payload(
        {
            "jobs": [
                {
                    "id": 101,
                    "title": "Backend Engineer",
                    "location": {"name": "Remote - US"},
                    "content": "<p>Use Python and PostgreSQL</p>",
                    "absolute_url": "https://boards.greenhouse.io/acme/jobs/101",
                    "departments": [{"name": "Engineering"}],
                }
            ]
        },
        company_name="Acme",
    )
    assert len(gh) == 1
    assert gh[0].work_mode == "remote"
    assert "Python" in gh[0].tags

    lever = parse_lever_payload(
        [
            {
                "id": "lv-1",
                "text": "Full Stack Engineer",
                "categories": {"location": "Tel Aviv", "team": "Product"},
                "workplaceType": "hybrid",
                "descriptionPlain": "React TypeScript FastAPI",
                "hostedUrl": "https://jobs.lever.co/acme/lv-1",
            }
        ],
        company_name="Acme",
    )
    assert len(lever) == 1
    assert lever[0].work_mode == "hybrid"

    ashby = parse_ashby_payload(
        {
            "organizationName": "BetaLabs",
            "jobs": [
                {
                    "id": "ash-1",
                    "title": "AI Engineer",
                    "location": "San Francisco",
                    "isRemote": False,
                    "descriptionPlain": "Python LLM RAG",
                    "jobUrl": "https://jobs.ashbyhq.com/betalabs/ash-1",
                }
            ],
        }
    )
    assert len(ashby) == 1
    assert ashby[0].company == "BetaLabs"

    remotive = parse_remotive_payload(
        {
            "jobs": [
                {
                    "id": 555,
                    "title": "Platform Engineer",
                    "company_name": "RemoteCo",
                    "candidate_required_location": "Worldwide",
                    "description": "<p>Docker Kubernetes</p>",
                    "url": "https://remotive.com/jobs/555",
                    "tags": ["Docker"],
                }
            ]
        }
    )
    assert remotive[0].work_mode == "remote"

    arbeitnow = parse_arbeitnow_payload(
        {
            "data": [
                {
                    "slug": "python-dev-1",
                    "title": "Python Developer",
                    "company_name": "EuroTech",
                    "location": "Berlin",
                    "remote": True,
                    "description": "FastAPI SQL",
                    "url": "https://www.arbeitnow.com/view/python-dev-1",
                    "tags": ["Python"],
                }
            ]
        }
    )
    assert arbeitnow[0].work_mode == "remote"

    # Deduplication check
    first_insert = upsert_normalized_jobs(db_session, gh + lever + ashby + remotive + arbeitnow)
    second_insert = upsert_normalized_jobs(db_session, gh + lever)
    assert first_insert == 5
    assert second_insert == 0


def test_manual_job_import(client):
    resp = client.post(
        "/api/jobs/import",
        json={
            "title": "Senior Python Engineer",
            "company": "Stripe",
            "location": "Remote",
            "work_mode": "remote",
            "description": "Build APIs with Python, FastAPI, and PostgreSQL.",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Senior Python Engineer"
    assert data["score"] is not None
    assert data["score"] > 0

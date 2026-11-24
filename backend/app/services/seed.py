from sqlalchemy.orm import Session

from app.models import Contact, Job, JobSource, LearnedRule, Profile
from app.services.outreach import normalize_company_name


def seed_default_sources_if_empty(db: Session) -> None:
    profile = db.query(Profile).first()
    if profile is None:
        profile = Profile(
            full_name="Job Seeker",
            headline="Software Engineer",
            skills=["Python", "TypeScript", "React", "FastAPI", "SQL"],
            target_roles=["Software Engineer", "Backend Engineer", "Full Stack Engineer"],
            preferred_locations=["Remote", "Tel Aviv"],
            work_mode="hybrid",
            experience_years=4,
            dealbreakers=["PHP", "Unpaid"],
            daily_pick_count=4,
            digest_days=["sun", "mon", "tue", "wed"],
            digest_hour=9,
            timezone="Asia/Jerusalem",
        )
        db.add(profile)
        db.commit()

    if db.query(JobSource).count() == 0:
        starter_sources = [
            JobSource(
                name="Remotive Software Dev",
                source_type="remotive",
                config={"category": "software-dev", "limit": 30},
                enabled=True,
            ),
            JobSource(
                name="Arbeitnow Tech Jobs",
                source_type="arbeitnow",
                config={"limit": 30},
                enabled=True,
            ),
            JobSource(
                name="Stripe (Greenhouse Example)",
                source_type="greenhouse",
                config={"board_token": "stripe", "company_name": "Stripe", "limit": 25},
                enabled=False,
            ),
            JobSource(
                name="Notion (Ashby Example)",
                source_type="ashby",
                config={"company_slug": "notion", "company_name": "Notion", "limit": 25},
                enabled=False,
            ),
        ]
        db.add_all(starter_sources)
        db.commit()


def load_demo_workspace(db: Session) -> dict[str, int]:
    """Populate realistic sample jobs, contacts, and learned rules for immediate offline testing."""
    seed_default_sources_if_empty(db)
    profile = db.query(Profile).first()
    if profile and not profile.resume_text.strip():
        profile.full_name = "Alex Rivera"
        profile.headline = "Senior Full-Stack & Backend Engineer (Python / React / Cloud)"
        profile.resume_filename = "sample_resume.txt"
        profile.resume_text = (
            "Alex Rivera — Senior Software Engineer (5+ years)\n"
            "Core stack: Python, FastAPI, TypeScript, React, PostgreSQL, SQLite, Docker, GCP Cloud Run.\n"
            "Led design of AI-assisted developer workflows, REST APIs, distributed background pipelines, "
            "and human-in-the-loop review dashboards. B.Sc. in Computer Science."
        )
        profile.skills = ["Python", "FastAPI", "TypeScript", "React", "PostgreSQL", "Docker", "GCP", "REST"]
        profile.target_roles = ["Senior Software Engineer", "Backend Engineer", "Full Stack Engineer", "AI Engineer"]
        profile.preferred_locations = ["Remote", "Tel Aviv", "New York"]
        profile.work_mode = "hybrid"
        profile.experience_years = 5
        profile.dealbreakers = ["PHP", "COBOL", "Unpaid"]
        db.commit()

    sample_jobs = [
        {
            "external_id": "demo-1",
            "title": "Senior Backend Engineer (Python & FastAPI)",
            "company": "Stripe",
            "location": "Remote (EMEA / US)",
            "work_mode": "remote",
            "url": "https://stripe.com/jobs",
            "description": "Build resilient payment APIs using Python, FastAPI, PostgreSQL, Docker, and cloud infrastructure. Collaborate across product teams on high-throughput REST services.",
            "tags": ["Python", "FastAPI", "PostgreSQL", "Docker", "REST"],
            "salary_text": "$175k - $210k",
        },
        {
            "external_id": "demo-2",
            "title": "Full Stack Engineer, AI Workflows",
            "company": "Notion",
            "location": "San Francisco / Hybrid",
            "work_mode": "hybrid",
            "url": "https://www.notion.so/careers",
            "description": "Craft human-in-the-loop AI interfaces with React, TypeScript, and Python backend services on GCP. Experience with LLM orchestration and clean UX is a plus.",
            "tags": ["React", "TypeScript", "Python", "GCP", "LLM"],
            "salary_text": "$165k - $205k",
        },
        {
            "external_id": "demo-3",
            "title": "Staff Platform Engineer",
            "company": "Datadog",
            "location": "Tel Aviv / Hybrid",
            "work_mode": "hybrid",
            "url": "https://careers.datadoghq.com",
            "description": "Architect observability pipelines with Go, Kubernetes, Kafka, Terraform, and Python tooling at scale.",
            "tags": ["Go", "Kubernetes", "Kafka", "Terraform", "Python"],
            "salary_text": "$190k - $230k",
        },
        {
            "external_id": "demo-4",
            "title": "Backend Software Engineer - Cloud Data",
            "company": "Linear",
            "location": "Remote",
            "work_mode": "remote",
            "url": "https://linear.app/careers",
            "description": "Work on sync engines, TypeScript, PostgreSQL, and developer APIs with high product polish.",
            "tags": ["TypeScript", "PostgreSQL", "REST", "Docker"],
            "salary_text": "$160k - $195k",
        },
        {
            "external_id": "demo-5",
            "title": "Product Engineer (React + Python)",
            "company": "Figma",
            "location": "Hybrid - Tel Aviv",
            "work_mode": "hybrid",
            "url": "https://www.figma.com/careers",
            "description": "Build collaborative web features with React, TypeScript, Python APIs, and GCP services.",
            "tags": ["React", "TypeScript", "Python", "GCP"],
            "salary_text": "$170k - $210k",
        },
        {
            "external_id": "demo-6",
            "title": "Junior PHP & WordPress Developer",
            "company": "Legacy Agency",
            "location": "Onsite - Austin",
            "work_mode": "onsite",
            "url": "https://example.com/php-job",
            "description": "Maintain legacy PHP plugins and MySQL databases onsite five days a week.",
            "tags": ["PHP", "MySQL"],
            "salary_text": "$65k - $80k",
        },
        {
            "external_id": "demo-7",
            "title": "Applied AI Engineer",
            "company": "Anthropic",
            "location": "San Francisco / Hybrid",
            "work_mode": "hybrid",
            "url": "https://www.anthropic.com/careers",
            "description": "Build evaluation pipelines, Python FastAPI services, and TypeScript tooling for safe human-in-the-loop AI systems.",
            "tags": ["Python", "FastAPI", "TypeScript", "LLM", "Docker"],
            "salary_text": "$210k - $270k",
        },
        {
            "external_id": "demo-8",
            "title": "Senior Frontend Engineer (React)",
            "company": "Vercel",
            "location": "Remote",
            "work_mode": "remote",
            "url": "https://vercel.com/careers",
            "description": "Lead developer dashboard experiences in React, TypeScript, Next.js, and REST/GraphQL APIs.",
            "tags": ["React", "TypeScript", "Next.js", "GraphQL"],
            "salary_text": "$170k - $205k",
        },
    ]

    jobs_added = 0
    for item in sample_jobs:
        exists = (
            db.query(Job)
            .filter(Job.source_type == "demo", Job.external_id == item["external_id"])
            .first()
        )
        if not exists:
            db.add(
                Job(
                    source_type="demo",
                    external_id=item["external_id"],
                    title=item["title"],
                    company=item["company"],
                    location=item["location"],
                    work_mode=item["work_mode"],
                    url=item["url"],
                    description=item["description"],
                    tags=item["tags"],
                    salary_text=item["salary_text"],
                    posted_at="2026-11-23",
                    status="new",
                )
            )
            jobs_added += 1

    sample_contacts = [
        {
            "name": "Maya Cohen",
            "company": "Stripe, Inc.",
            "role": "Staff Software Engineer",
            "linkedin_url": "https://www.linkedin.com/in/maya-cohen-example",
            "email": "maya.cohen@example.com",
            "relationship": "former_colleague",
            "notes": "Worked together on payments microservices in 2023.",
        },
        {
            "name": "Daniel Kim",
            "company": "Notion",
            "role": "Engineering Manager",
            "linkedin_url": "https://www.linkedin.com/in/daniel-kim-example",
            "email": "",
            "relationship": "1st_degree",
            "notes": "Met at AI Engineering meetup.",
        },
        {
            "name": "Noa Levi",
            "company": "Figma",
            "role": "Senior Product Engineer",
            "linkedin_url": "https://www.linkedin.com/in/noa-levi-example",
            "email": "",
            "relationship": "alumni",
            "notes": "Same CS graduating class.",
        },
        {
            "name": "Jordan Patel",
            "company": "Datadog",
            "role": "Technical Recruiter",
            "linkedin_url": "https://www.linkedin.com/in/jordan-patel-example",
            "email": "jordan.p@example.com",
            "relationship": "recruiter",
            "notes": "Reached out about Tel Aviv platform roles.",
        },
    ]

    contacts_added = 0
    for c in sample_contacts:
        exists = db.query(Contact).filter(Contact.name == c["name"]).first()
        if not exists:
            db.add(
                Contact(
                    name=c["name"],
                    company=c["company"],
                    normalized_company=normalize_company_name(c["company"]),
                    role=c["role"],
                    linkedin_url=c["linkedin_url"],
                    email=c["email"],
                    relationship=c["relationship"],
                    notes=c["notes"],
                    source="manual",
                )
            )
            contacts_added += 1

    sample_rules = [
        {"category": "skill", "term": "FastAPI", "weight": 4.0, "source": "learned"},
        {"category": "work_mode", "term": "remote", "weight": 3.0, "source": "learned"},
    ]
    rules_added = 0
    for r in sample_rules:
        exists = (
            db.query(LearnedRule)
            .filter(LearnedRule.category == r["category"], LearnedRule.term == r["term"])
            .first()
        )
        if not exists:
            db.add(LearnedRule(category=r["category"], term=r["term"], weight=r["weight"], source=r["source"]))
            rules_added += 1

    db.commit()
    return {"jobs_added": jobs_added, "contacts_added": contacts_added, "rules_added": rules_added}

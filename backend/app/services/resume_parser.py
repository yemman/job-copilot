import io
import re
from pypdf import PdfReader

CURATED_SKILLS: list[str] = [
    "Python", "TypeScript", "JavaScript", "React", "Next.js", "Vue", "Angular",
    "FastAPI", "Django", "Flask", "Node.js", "Express", "NestJS", "Go", "Rust",
    "Java", "Spring Boot", "Kotlin", "C#", ".NET", "C++", "Ruby", "Rails", "PHP",
    "SQL", "PostgreSQL", "MySQL", "SQLite", "MongoDB", "Redis", "Elasticsearch",
    "GraphQL", "REST", "gRPC", "Kafka", "RabbitMQ", "Celery",
    "Docker", "Kubernetes", "Terraform", "Ansible", "Linux", "Git", "CI/CD",
    "GitHub Actions", "AWS", "GCP", "Google Cloud", "Azure", "Cloud Run",
    "BigQuery", "Snowflake", "Spark", "Airflow", "dbt", "Pandas", "NumPy",
    "PyTorch", "TensorFlow", "Scikit-learn", "LangChain", "LLM", "RAG", "AI",
    "Machine Learning", "Data Engineering", "Microservices", "Distributed Systems",
    "HTML", "CSS", "Tailwind CSS", "Vite", "Playwright", "Pytest", "Jest",
    "Product Management", "System Design", "API Design", "Security", "OAuth",
    "Prometheus", "Grafana", "Datadog", "OpenTelemetry", "Serverless",
]


def extract_resume_text(filename: str, content: bytes) -> str:
    """Extract plain text from PDF, TXT, or Markdown resume bytes."""
    lower = (filename or "").lower()
    if lower.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(content))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(pages).strip()
        return text
    try:
        return content.decode("utf-8").strip()
    except UnicodeDecodeError:
        return content.decode("latin-1", errors="ignore").strip()


def extract_skills_from_text(text: str) -> list[str]:
    """Detect known technical/domain skills from text using boundary-aware matching."""
    if not text:
        return []
    found: list[str] = []
    lowered = text.lower()
    for skill in CURATED_SKILLS:
        s_low = skill.lower()
        # Escape regex special chars like C++, C#, .NET, Next.js
        escaped = re.escape(s_low)
        pattern = rf"(?<![a-z0-9]){escaped}(?![a-z0-9])"
        if re.search(pattern, lowered):
            found.append(skill)
    return found

import csv
import io
import re
from urllib.parse import quote_plus

from sqlalchemy.orm import Session

from app.models import Contact, Job, Profile
from app.services.gemini_client import generate_json

COMPANY_SUFFIXES = {
    "inc", "incorporated", "ltd", "limited", "llc", "corp", "corporation",
    "co", "company", "gmbh", "plc", "technologies", "technology", "labs", "ai",
}


def normalize_company_name(name: str) -> str:
    if not name:
        return ""
    cleaned = re.sub(r"[^\w\s]", " ", name.lower())
    tokens = [t for t in cleaned.split() if t and t not in COMPANY_SUFFIXES]
    return " ".join(tokens) if tokens else re.sub(r"\s+", " ", cleaned).strip()


def find_matching_contacts(db: Session, company: str) -> list[Contact]:
    norm = normalize_company_name(company)
    if not norm:
        return []
    contacts = db.query(Contact).all()
    matches: list[Contact] = []
    for c in contacts:
        c_norm = c.normalized_company or normalize_company_name(c.company)
        if not c_norm:
            continue
        if c_norm == norm or norm in c_norm or c_norm in norm:
            matches.append(c)
    return matches


def build_linkedin_people_search_url(company: str, role_hint: str = "") -> str:
    query = f"{company} {role_hint}".strip()
    return f"https://www.linkedin.com/search/results/people/?keywords={quote_plus(query)}"


def parse_linkedin_connections_csv(raw_bytes: bytes) -> list[dict[str, str]]:
    """Parse LinkedIn Connections.csv, skipping preamble note lines before the header row."""
    try:
        text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw_bytes.decode("latin-1", errors="ignore")

    lines = text.splitlines()
    header_idx: int | None = None
    for idx, line in enumerate(lines[:15]):
        low = line.lower()
        if "first name" in low and ("last name" in low or "company" in low):
            header_idx = idx
            break
    if header_idx is None:
        return []

    reader = csv.DictReader(io.StringIO("\n".join(lines[header_idx:])))
    parsed: list[dict[str, str]] = []
    for row in reader:
        norm_row = {str(k).strip().lower(): (v or "").strip() for k, v in row.items() if k}
        first = norm_row.get("first name", "")
        last = norm_row.get("last name", "")
        full_name = f"{first} {last}".strip()
        if not full_name:
            continue
        parsed.append(
            {
                "name": full_name,
                "company": norm_row.get("company", ""),
                "role": norm_row.get("position", "") or norm_row.get("title", ""),
                "linkedin_url": norm_row.get("url", "") or norm_row.get("profile url", ""),
                "email": norm_row.get("email address", "") or norm_row.get("email", ""),
                "connected_on": norm_row.get("connected on", ""),
            }
        )
    return parsed


def _clamp_connect_note(text: str, max_len: int = 300) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= max_len:
        return cleaned
    trimmed = cleaned[: max_len - 3].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return f"{trimmed}..."


def draft_outreach_message(
    job: Job,
    profile: Profile,
    contact: Contact | None,
    contact_name: str,
    channel: str,
) -> dict[str, str]:
    """Draft a personalized outreach message using Gemini if configured, else clean templates."""
    recipient_name = (contact.name if contact else contact_name) or "there"
    first_name = recipient_name.split()[0] if recipient_name != "there" else "there"
    sender_name = profile.full_name or "Candidate"
    skills = (profile.skills or [])[:3]
    skills_str = ", ".join(skills) if skills else "software engineering"
    matched = (job.score_breakdown or {}).get("matched_skills") or skills[:2]
    matched_str = ", ".join(matched[:3]) if matched else skills_str
    rel_note = ""
    if contact and contact.relationship in {"former_colleague", "alumni", "1st_degree"}:
        rel_note = f"Relationship: {contact.relationship} ({contact.role} at {contact.company})"

    prompt = (
        f"Draft a concise, authentic, non-salesy outreach message for a job seeker.\n"
        f"Sender: {sender_name} ({profile.headline or 'Candidate'}, skills: {skills_str})\n"
        f"Recipient: {recipient_name} {rel_note}\n"
        f"Target Role: {job.title} at {job.company}\n"
        f"Matched skills: {matched_str}\n"
        f"Channel: {channel}\n"
        f"Rules:\n"
        f"- If channel is linkedin_connect_note, body MUST be <= 290 characters total.\n"
        f"- Return JSON with keys: subject (string, empty for LinkedIn), body (string).\n"
    )
    ai_res = generate_json(
        prompt=prompt,
        system_instruction="You write brief, respectful networking outreach messages for human review.",
    )
    if ai_res and isinstance(ai_res.get("body"), str) and ai_res["body"].strip():
        body = ai_res["body"].strip()
        subject = str(ai_res.get("subject") or "").strip()
        if channel == "linkedin_connect_note":
            body = _clamp_connect_note(body, 300)
            subject = ""
        return {"subject": subject, "body": body}

    # Deterministic template fallback
    if channel == "linkedin_connect_note":
        note = (
            f"Hi {first_name}, I saw the {job.title} opening at {job.company}. "
            f"With {profile.experience_years}+ yrs in {matched_str}, I'd love to connect and learn about the team before applying."
        )
        return {"subject": "", "body": _clamp_connect_note(note, 300)}

    if channel == "email":
        subject = f"Quick question about {job.title} at {job.company}"
        body = (
            f"Hi {first_name},\n\n"
            f"I came across the {job.title} role at {job.company} and noticed your work there. "
            f"My background focuses on {matched_str} ({profile.experience_years}+ years of experience), "
            f"which aligns closely with what the team is looking for.\n\n"
            f"Before submitting a formal application, I'd really appreciate a quick 5-minute perspective on the team "
            f"or whether there's a referral path you'd be comfortable sharing.\n\n"
            f"Best regards,\n{sender_name}"
        )
        return {"subject": subject, "body": body}

    # linkedin_dm
    body = (
        f"Hi {first_name} — hope you're doing well! I saw the {job.title} role at {job.company} "
        f"and it looks like a strong match with my background in {matched_str}. "
        f"Before I apply, would you be open to sharing a quick perspective on the team or pointing me to the right person?"
    )
    return {"subject": "", "body": body}

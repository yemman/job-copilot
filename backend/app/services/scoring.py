import re
from typing import Any

from app.models import FeedbackEvent, Job, LearnedRule, Profile
from app.services.gemini_client import generate_json, is_gemini_enabled
from app.services.outreach import normalize_company_name
from app.services.resume_parser import extract_skills_from_text


def _contains_term(text: str, term: str) -> bool:
    if not term:
        return False
    escaped = re.escape(term.strip().lower())
    return bool(re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", text))


def _resume_overlap_points(resume_text: str, job_blob: str) -> float:
    if not resume_text:
        return 0.0
    words = {
        w for w in re.findall(r"[a-zA-Z]{4,}", resume_text.lower())
        if w not in {"with", "that", "this", "from", "have", "will", "your", "team", "work", "experience"}
    }
    if not words:
        return 0.0
    job_words = set(re.findall(r"[a-zA-Z]{4,}", job_blob))
    overlap = len(words & job_words)
    return min(12.0, overlap * 0.8)


def _rule_matches_job(rule: LearnedRule, job: Job, job_blob: str, job_skills_lower: set[str]) -> bool:
    term = (rule.term or "").strip().lower()
    if not term:
        return False
    cat = rule.category
    if cat == "skill":
        return term in job_skills_lower or _contains_term(job_blob, term)
    if cat == "title_keyword":
        return _contains_term(job.title.lower(), term)
    if cat == "company":
        return normalize_company_name(job.company) == normalize_company_name(term) or term in job.company.lower()
    if cat == "work_mode":
        return (job.work_mode or "").lower() == term
    if cat == "location":
        return term in (job.location or "").lower()
    if cat == "red_flag":
        return _contains_term(job_blob, term)
    return False


def score_job(
    job: Job,
    profile: Profile,
    learned_rules: list[LearnedRule],
    recent_feedback: list[FeedbackEvent] | None = None,
    use_ai: bool = True,
) -> tuple[float, dict[str, Any]]:
    title_low = (job.title or "").lower()
    desc_low = (job.description or "").lower()
    tags_low = [str(t).lower() for t in (job.tags or [])]
    job_blob = f"{title_low}\n{desc_low}\n{' '.join(tags_low)}"

    job_detected_skills = extract_skills_from_text(f"{job.title}\n{job.description}\n{' '.join(job.tags or [])}")
    job_skills_lower = {s.lower() for s in job_detected_skills} | set(tags_low)

    profile_skills = [s.strip() for s in (profile.skills or []) if s.strip()]
    matched_skills: list[str] = []
    missing_skills: list[str] = []

    for sk in profile_skills:
        sk_low = sk.lower()
        if sk_low in job_skills_lower or _contains_term(job_blob, sk_low):
            matched_skills.append(sk)
        else:
            missing_skills.append(sk)

    # Skills in the job that aren't in user's profile skills
    profile_skills_lower = {s.lower() for s in profile_skills}
    job_gaps = [s for s in job_detected_skills if s.lower() not in profile_skills_lower][:6]

    # 1. Skill overlap (up to 45 pts)
    if profile_skills:
        # Reward matching at least 4+ skills strongly, not punishing for having a long skill list
        denom = min(len(profile_skills), max(len(job_detected_skills), 4))
        skill_pts = min(45.0, (len(matched_skills) / max(denom, 1)) * 45.0)
    else:
        skill_pts = 20.0

    # 2. Target role alignment (up to 25 pts)
    target_roles = [r.strip().lower() for r in (profile.target_roles or []) if r.strip()]
    role_pts = 0.0
    if not target_roles:
        role_pts = 12.0
    else:
        best_ratio = 0.0
        for role in target_roles:
            if role in title_low:
                best_ratio = 1.0
                break
            tokens = [t for t in role.split() if len(t) > 2]
            if tokens:
                hits = sum(1 for t in tokens if t in title_low)
                best_ratio = max(best_ratio, hits / len(tokens))
        role_pts = best_ratio * 25.0

    # 3. Work mode & location match (up to 15 pts)
    pref_mode = (profile.work_mode or "any").lower()
    job_mode = (job.work_mode or "unknown").lower()
    mode_pts = 0.0
    if pref_mode == "any" or job_mode == pref_mode:
        mode_pts += 9.0
    elif job_mode == "unknown":
        mode_pts += 4.5
    elif pref_mode == "hybrid" and job_mode == "remote":
        mode_pts += 6.0

    pref_locs = [l.strip().lower() for l in (profile.preferred_locations or []) if l.strip()]
    job_loc_low = (job.location or "").lower()
    if not pref_locs or job_mode == "remote" or any(loc in job_loc_low for loc in pref_locs):
        mode_pts += 6.0

    # 4. Resume keyword overlap + freshness/description richness (up to 15 pts)
    resume_pts = _resume_overlap_points(profile.resume_text or "", job_blob)
    richness_pts = 3.0 if len(desc_low) > 200 else 1.0

    # 5. Dealbreakers penalty (-25 pts per match)
    dealbreakers_hit: list[str] = []
    for db_term in (profile.dealbreakers or []):
        if db_term.strip() and _contains_term(job_blob, db_term.strip().lower()):
            dealbreakers_hit.append(db_term.strip())
    dealbreaker_penalty = len(dealbreakers_hit) * 25.0

    base_score = max(0.0, min(100.0, skill_pts + role_pts + mode_pts + resume_pts + richness_pts - dealbreaker_penalty))

    # 6. Learned rules adjustment (clamped [-25, +25])
    applied_rules: list[dict[str, Any]] = []
    raw_learned = 0.0
    for rule in learned_rules:
        if not rule.enabled:
            continue
        if _rule_matches_job(rule, job, job_blob, job_skills_lower):
            raw_learned += float(rule.weight)
            applied_rules.append(
                {
                    "id": rule.id,
                    "category": rule.category,
                    "term": rule.term,
                    "weight": round(float(rule.weight), 2),
                }
            )
    learned_adjustment = max(-25.0, min(25.0, raw_learned))

    # 7. Optional Gemini AI rerank & rationale
    ai_adjustment = 0.0
    scorer_mode = "heuristic"
    rationale = ""

    if use_ai and is_gemini_enabled():
        rules_summary = [
            f"{r['category']}:{r['term']} ({r['weight']:+.1f})" for r in applied_rules[:8]
        ]
        fb_summary = []
        for fb in (recent_feedback or [])[:8]:
            snap = fb.job_snapshot or {}
            fb_summary.append(
                f"{fb.event_type} on {snap.get('title', '?')} @ {snap.get('company', '?')} "
                f"(reason={fb.reason_code or 'none'})"
            )
        prompt = (
            f"Evaluate job fit for candidate.\n"
            f"Candidate: {profile.headline}; skills={profile_skills[:20]}; "
            f"target_roles={profile.target_roles}; work_mode={profile.work_mode}; "
            f"locations={profile.preferred_locations}; experience_years={profile.experience_years}; "
            f"dealbreakers={profile.dealbreakers}; notes={profile.notes_for_ai[:300]}\n"
            f"Resume excerpt: {(profile.resume_text or '')[:1200]}\n\n"
            f"Job: {job.title} at {job.company} | location={job.location} | work_mode={job.work_mode}\n"
            f"Tags: {job.tags}\n"
            f"Description excerpt: {(job.description or '')[:1600]}\n\n"
            f"Base heuristic score: {base_score:.1f}, Learned rules applied: {rules_summary}\n"
            f"Recent human feedback: {fb_summary}\n\n"
            f"Return JSON with keys: ai_adjustment (number between -15 and 15), "
            f"rationale (2 concise sentences explaining strengths, gaps, and connection to past feedback)."
        )
        ai_res = generate_json(
            prompt=prompt,
            system_instruction="You are a precise career matching assistant. Output valid JSON only.",
        )
        if ai_res:
            try:
                adj = float(ai_res.get("ai_adjustment", 0.0))
                ai_adjustment = max(-15.0, min(15.0, adj))
                if isinstance(ai_res.get("rationale"), str) and ai_res["rationale"].strip():
                    rationale = ai_res["rationale"].strip()
                    scorer_mode = "gemini"
            except (TypeError, ValueError):
                pass

    if not rationale:
        parts = []
        if matched_skills:
            parts.append(f"Matches {len(matched_skills)} key skills ({', '.join(matched_skills[:5])}).")
        else:
            parts.append("Low direct skill keyword overlap with your saved skills.")
        if dealbreakers_hit:
            parts.append(f"Dealbreaker hit: {', '.join(dealbreakers_hit)}.")
        elif applied_rules:
            top_rule = max(applied_rules, key=lambda r: abs(r["weight"]))
            direction = "boosted" if top_rule["weight"] > 0 else "penalized"
            parts.append(
                f"Learned preference {direction} score for {top_rule['category']} '{top_rule['term']}' ({top_rule['weight']:+.1f})."
            )
        if job_gaps:
            parts.append(f"Notable gaps/extras mentioned: {', '.join(job_gaps[:3])}.")
        rationale = " ".join(parts)

    final_score = round(max(0.0, min(100.0, base_score + learned_adjustment + ai_adjustment)), 1)

    breakdown = {
        "base_score": round(base_score, 1),
        "learned_adjustment": round(learned_adjustment, 1),
        "ai_adjustment": round(ai_adjustment, 1),
        "matched_skills": matched_skills,
        "missing_skills": job_gaps if job_gaps else missing_skills[:5],
        "dealbreakers_hit": dealbreakers_hit,
        "applied_rules": applied_rules,
        "rationale": rationale,
        "scorer_mode": scorer_mode,
    }
    return final_score, breakdown

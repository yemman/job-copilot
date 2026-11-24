from app.models import Job, LearnedRule, Profile
from app.services.learning import record_feedback_and_learn
from app.services.scoring import score_job


def test_scoring_dealbreaker_and_learning_loop(db_session):
    profile = db_session.query(Profile).first()
    profile.skills = ["Python", "FastAPI", "React", "TypeScript"]
    profile.target_roles = ["Backend Engineer", "Full Stack Engineer"]
    profile.work_mode = "remote"
    profile.dealbreakers = ["PHP"]
    db_session.commit()

    good_job = Job(
        source_type="manual",
        external_id="g1",
        title="Backend Engineer",
        company="GoodCorp",
        location="Remote",
        work_mode="remote",
        description="Python FastAPI React TypeScript distributed backend systems.",
        tags=["Python", "FastAPI"],
    )
    bad_job = Job(
        source_type="manual",
        external_id="b1",
        title="PHP Developer",
        company="LegacyCorp",
        location="Onsite",
        work_mode="onsite",
        description="Legacy PHP maintenance.",
        tags=["PHP"],
    )
    db_session.add_all([good_job, bad_job])
    db_session.commit()

    good_score_before, good_bd = score_job(good_job, profile, [], [], use_ai=False)
    bad_score, bad_bd = score_job(bad_job, profile, [], [], use_ai=False)
    assert good_score_before > bad_score
    assert "PHP" in bad_bd["dealbreakers_hit"]
    assert "Python" in good_bd["matched_skills"]

    # Record positive feedback (interview invited) -> should create positive rules
    _, rules = record_feedback_and_learn(
        db_session, event_type="interview_invited", job=good_job
    )
    assert len(rules) > 0

    all_rules = db_session.query(LearnedRule).all()
    good_score_after, after_bd = score_job(good_job, profile, all_rules, [], use_ai=False)
    assert good_score_after > good_score_before
    assert after_bd["learned_adjustment"] > 0

    # Negative skip feedback
    staff_job = Job(
        source_type="manual",
        external_id="s1",
        title="Staff Blockchain Engineer",
        company="SkipCorp",
        location="Onsite - NYC",
        work_mode="onsite",
        description="Solidity Rust staff role.",
        tags=["Rust"],
    )
    db_session.add(staff_job)
    db_session.commit()

    _, skip_rules = record_feedback_and_learn(
        db_session,
        event_type="digest_skip",
        job=staff_job,
        reason_code="company_not_interesting",
        note="avoid crypto",
    )
    terms = {r.term for r in skip_rules}
    assert "skipcorp" in terms or "SkipCorp" in terms
    assert "crypto" in terms


def test_locked_rule_is_immune_to_feedback(db_session):
    locked_rule = LearnedRule(
        category="skill",
        term="Python",
        weight=10.0,
        source="manual",
        locked=True,
        enabled=True,
    )
    db_session.add(locked_rule)
    db_session.commit()

    job = Job(
        source_type="manual",
        external_id="lk1",
        title="Python Engineer",
        company="TestCo",
        work_mode="remote",
        description="Python engineering role.",
        tags=["Python"],
    )
    db_session.add(job)
    db_session.commit()

    record_feedback_and_learn(db_session, event_type="offer_received", job=job)
    db_session.refresh(locked_rule)
    assert locked_rule.weight == 10.0

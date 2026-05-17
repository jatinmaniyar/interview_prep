"""Weighted JobScore for the SDE-2/Senior persona.

JobScore =
    0.35 * role_relevance       # how well the role matches mid/senior backend persona
  + 0.20 * profile_match        # user profile fit (titles/companies/stack/seniority)
  + 0.15 * engineering_quality  # company tier + stack sophistication + system design
  + 0.10 * compensation         # vs profile target or absolute USD bands
  + 0.10 * company_growth       # hiring velocity + tier
  + 0.05 * referral_probability # warm contacts at the company
  + 0.05 * hiring_urgency       # freshness + repost behaviour

Each component is normalized to [0, 1]. Higher is better.

career_leverage is computed and persisted on the row but kept out of the
top-line score (it's exposed in the breakdown so the dashboard can sort
by it independently — "which of these roles will most help me get to L5?").
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from app.models import Company, JobPosting, UserJobProfile, WarmContact
from sqlalchemy.orm import Session
from sqlalchemy import func, select

WEIGHTS = {
    "role_relevance": 0.35,
    "profile_match": 0.20,
    "engineering_quality": 0.15,
    "compensation": 0.10,
    "company_growth": 0.10,
    "referral_probability": 0.05,
    "hiring_urgency": 0.05,
}


@dataclass
class Breakdown:
    role_relevance: float
    profile_match: float
    engineering_quality: float
    compensation: float
    company_growth: float
    referral_probability: float
    hiring_urgency: float
    # informational only — surfaced in JSON but not in total()
    career_leverage: float
    competition_score: float

    def total(self) -> float:
        return sum(getattr(self, k) * w for k, w in WEIGHTS.items())

    def as_json(self) -> str:
        return json.dumps({
            **{k: round(getattr(self, k), 3) for k in WEIGHTS},
            "career_leverage": round(self.career_leverage, 3),
            "competition_score": round(self.competition_score, 3),
            "weights": WEIGHTS,
        })


def _profile_match(job: JobPosting, profile: UserJobProfile | None) -> float:
    if not profile:
        return 0.5
    score = 0.0
    parts = 0

    target_titles = json.loads(profile.target_titles_json or "[]")
    if target_titles:
        parts += 1
        nt = (job.title_normalized or job.title or "").lower()
        if any(t.lower() in nt for t in target_titles):
            score += 1.0

    target_companies = {c.lower() for c in json.loads(profile.target_companies_json or "[]")}
    if target_companies:
        parts += 1
        if (job.company_name or "").lower() in target_companies:
            score += 1.0

    stack = json.loads(profile.stack_json or "[]")
    if stack:
        parts += 1
        job_stack = set(json.loads(job.stack_json or "[]"))
        overlap = job_stack & {s.lower() for s in stack}
        if job_stack:
            score += len(overlap) / max(len(job_stack), 1)

    if profile.seniority:
        parts += 1
        if job.seniority == profile.seniority:
            score += 1.0
        elif job.seniority and profile.seniority:
            # adjacent levels still get partial credit (mid<->senior, senior<->staff)
            ladder = ["intern", "junior", "mid", "senior", "staff", "principal"]
            try:
                gap = abs(ladder.index(job.seniority) - ladder.index(profile.seniority))
                score += max(0.0, 1.0 - 0.4 * gap)
            except ValueError:
                score += 0.3

    if profile.preferred_remote:
        parts += 1
        if job.remote == profile.preferred_remote:
            score += 1.0

    if profile.needs_visa:
        parts += 1
        if job.visa_sponsorship is True:
            score += 1.0
        elif job.visa_sponsorship is False:
            score += 0.0
        else:
            score += 0.4

    return score / parts if parts else 0.5


def _compensation(job: JobPosting, profile: UserJobProfile | None) -> float:
    if not job.salary_max:
        return 0.3
    if not profile or not profile.target_min_comp:
        if job.salary_max >= 400_000: return 1.0
        if job.salary_max >= 250_000: return 0.85
        if job.salary_max >= 150_000: return 0.6
        return 0.3
    ratio = job.salary_max / max(profile.target_min_comp, 1)
    if ratio >= 1.5: return 1.0
    if ratio >= 1.2: return 0.85
    if ratio >= 1.0: return 0.7
    if ratio >= 0.8: return 0.4
    return 0.15


def _referral(job: JobPosting, db: Session) -> float:
    if not job.company_id:
        return 0.0
    n = db.execute(
        select(func.count()).select_from(WarmContact).where(WarmContact.company_id == job.company_id)
    ).scalar_one() or 0
    if n == 0: return 0.0
    if n >= 5: return 1.0
    return 0.2 + 0.16 * n


def _company_growth(company: Company | None) -> float:
    if not company:
        return 0.4
    tier_bump = {"faang": 0.7, "unicorn": 0.8, "startup": 0.6, "enterprise": 0.5, "public": 0.55}.get(
        company.tier or "", 0.4
    )
    velocity = min((company.hiring_velocity_30d or 0) / 50.0, 1.0)
    return min(1.0, 0.5 * tier_bump + 0.5 * velocity)


def compute(job: JobPosting, profile: UserJobProfile | None, company: Company | None, db: Session) -> Breakdown:
    return Breakdown(
        role_relevance=max(0.0, min(1.0, job.role_relevance or 0.0)),
        profile_match=_profile_match(job, profile),
        engineering_quality=max(0.0, min(1.0, job.engineering_quality or 0.0)),
        compensation=_compensation(job, profile),
        company_growth=_company_growth(company),
        referral_probability=_referral(job, db),
        hiring_urgency=max(0.0, min(1.0, job.hiring_urgency or 0.0)),
        career_leverage=max(0.0, min(1.0, job.career_leverage or 0.0)),
        competition_score=max(0.0, 1.0 - (job.competition_score or 0.5)),
    )


def rescore_all(db: Session) -> int:
    """Recompute job_score for every active job. Low-signal rows score to 0."""
    profile = db.get(UserJobProfile, 1)
    companies = {c.id: c for c in db.execute(select(Company)).scalars().all()}
    jobs = db.execute(select(JobPosting).where(JobPosting.is_active == True)).scalars().all()  # noqa: E712
    n = 0
    for job in jobs:
        comp = companies.get(job.company_id) if job.company_id else None
        bd = compute(job, profile, comp, db)
        if job.is_low_signal:
            # Hard zero so even sort-by-anything won't surface them
            job.job_score = 0.0
        else:
            job.job_score = round(bd.total(), 4)
        job.score_breakdown_json = bd.as_json()
        n += 1
    db.commit()
    return n

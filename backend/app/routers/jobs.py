"""Job intelligence API.

Endpoints
    GET    /api/jobs                        list + filter
    GET    /api/jobs/{id}                   detail
    POST   /api/jobs/rescore                recompute scores
    GET    /api/jobs/facets                 distinct values for filters
    GET    /api/dashboard/trends            hiring trends + dream-company spikes
    GET    /api/companies                   intentionally namespaced below
    GET    /api/co/{slug}                   company detail + recent roles
    GET    /api/co                          list companies (sorted)
    GET    /api/sources                     ingestion registry status
    POST   /api/sources                     add (source, external_org) entry
    DELETE /api/sources/{source}/{org}      remove
    GET    /api/profile                     get user profile
    PUT    /api/profile                     update profile (triggers rescore)
    GET    /api/warm-contacts?company={id}  list contacts
    POST   /api/warm-contacts               add contact
    GET    /api/outreach?...                list drafts
    POST   /api/outreach                    save a draft
    PATCH  /api/outreach/{id}               update status/body
    GET    /api/applications                list tracker
    POST   /api/applications                create
    PATCH  /api/applications/{id}           update status
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import (
    Application,
    Company,
    CompanyNews,
    JobPosting,
    JobSourceRegistry,
    OutreachDraft,
    UserJobProfile,
    WarmContact,
)
from app.services.jobs import scoring

router = APIRouter(tags=["jobs"])


# ---------- jobs ----------

def _job_row(j: JobPosting) -> dict:
    return {
        "id": j.id,
        "source": j.source,
        "title": j.title,
        "title_normalized": j.title_normalized,
        "company_id": j.company_id,
        "company_name": j.company_name,
        "seniority": j.seniority,
        "role_family": j.role_family,
        "yoe_min": j.yoe_min,
        "yoe_max": j.yoe_max,
        "location": j.location,
        "remote": j.remote,
        "country": j.country,
        "salary_min": j.salary_min,
        "salary_max": j.salary_max,
        "salary_currency": j.salary_currency,
        "salary_band": j.salary_band,
        "visa_sponsorship": j.visa_sponsorship,
        "stack": json.loads(j.stack_json or "[]"),
        "url": j.url,
        "posted_at": j.posted_at.isoformat() if j.posted_at else None,
        "first_seen_at": j.first_seen_at.isoformat(),
        "last_seen_at": j.last_seen_at.isoformat(),
        "repost_count": j.repost_count,
        "is_active": j.is_active,
        "is_low_signal": j.is_low_signal,
        "has_system_design": j.has_system_design,
        "interview_style": j.interview_style,
        "hiring_urgency": j.hiring_urgency,
        "competition_score": j.competition_score,
        "role_relevance": j.role_relevance,
        "engineering_quality": j.engineering_quality,
        "career_leverage": j.career_leverage,
        "job_score": j.job_score,
        "duplicate_of": j.duplicate_of,
        "ai_summary_md": j.ai_summary_md,
    }


# Persona defaults — the platform is curated for SDE-2/Senior backend candidates.
# These kick in when the caller doesn't override seniority/role_family explicitly.
PERSONA_DEFAULT_SENIORITY = ["mid", "senior", "staff"]
PERSONA_DEFAULT_ROLE_FAMILIES = [
    "backend", "fullstack", "platform", "distributed",
    "infra", "api", "product_eng",
]


@router.get("/jobs")
def list_jobs(
    q: str | None = None,
    company: list[str] | None = Query(default=None),
    company_id: int | None = None,
    source: list[str] | None = Query(default=None),
    seniority: list[str] | None = Query(default=None),
    role_family: list[str] | None = Query(default=None),
    remote: list[str] | None = Query(default=None),
    country: list[str] | None = Query(default=None),
    tier: list[str] | None = Query(default=None),
    band: list[str] | None = Query(default=None),
    interview_style: list[str] | None = Query(default=None),
    min_salary: int | None = None,
    min_yoe: int | None = None,
    max_yoe: int | None = None,
    min_relevance: float | None = None,
    visa: bool | None = None,
    min_urgency: float | None = None,
    posted_within_days: int | None = None,
    only_active: bool = True,
    exclude_duplicates: bool = True,
    exclude_low_signal: bool = True,
    persona_default: bool = True,
    sort: str = "score",  # score|posted|salary|urgency|relevance|leverage|quality
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """List jobs.

    Persona defaults: when `persona_default=True` (the default) and the caller
    didn't supply `seniority` or `role_family`, we narrow to the SDE-2/Senior
    backend persona. Pass `persona_default=false` to see everything.
    """
    # Apply persona defaults *only* if the caller didn't pin those facets explicitly.
    if persona_default:
        if not seniority:
            seniority = PERSONA_DEFAULT_SENIORITY
        if not role_family:
            role_family = PERSONA_DEFAULT_ROLE_FAMILIES

    stmt = select(JobPosting)
    if only_active:
        stmt = stmt.where(JobPosting.is_active == True)  # noqa: E712
    if exclude_duplicates:
        stmt = stmt.where(JobPosting.duplicate_of.is_(None))
    if exclude_low_signal:
        stmt = stmt.where(JobPosting.is_low_signal == False)  # noqa: E712
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(JobPosting.title).like(like),
                func.lower(JobPosting.company_name).like(like),
                func.lower(JobPosting.location).like(like),
            )
        )
    if company:
        stmt = stmt.where(JobPosting.company_name.in_(company))
    if company_id is not None:
        stmt = stmt.where(JobPosting.company_id == company_id)
    if source:
        stmt = stmt.where(JobPosting.source.in_(source))
    if seniority:
        stmt = stmt.where(JobPosting.seniority.in_(seniority))
    if role_family:
        stmt = stmt.where(JobPosting.role_family.in_(role_family))
    if remote:
        stmt = stmt.where(JobPosting.remote.in_(remote))
    if country:
        stmt = stmt.where(JobPosting.country.in_(country))
    if band:
        stmt = stmt.where(JobPosting.salary_band.in_(band))
    if interview_style:
        stmt = stmt.where(JobPosting.interview_style.in_(interview_style))
    if tier:
        stmt = stmt.join(Company, Company.id == JobPosting.company_id).where(Company.tier.in_(tier))
    if min_salary:
        stmt = stmt.where(JobPosting.salary_max >= min_salary)
    if min_yoe is not None:
        # Either the role's yoe_min is at least min_yoe, OR yoe is unknown (don't over-filter).
        stmt = stmt.where(or_(JobPosting.yoe_min.is_(None), JobPosting.yoe_min >= min_yoe))
    if max_yoe is not None:
        stmt = stmt.where(or_(JobPosting.yoe_min.is_(None), JobPosting.yoe_min <= max_yoe))
    if min_relevance is not None:
        stmt = stmt.where(JobPosting.role_relevance >= min_relevance)
    if visa is not None:
        stmt = stmt.where(JobPosting.visa_sponsorship.is_(visa))
    if min_urgency is not None:
        stmt = stmt.where(JobPosting.hiring_urgency >= min_urgency)
    if posted_within_days:
        cutoff = datetime.utcnow() - timedelta(days=posted_within_days)
        stmt = stmt.where(
            or_(JobPosting.posted_at >= cutoff, JobPosting.first_seen_at >= cutoff)
        )

    sort_map = {
        "score": desc(JobPosting.job_score),
        "relevance": desc(JobPosting.role_relevance),
        "leverage": desc(JobPosting.career_leverage),
        "quality": desc(JobPosting.engineering_quality),
        "posted": desc(func.coalesce(JobPosting.posted_at, JobPosting.first_seen_at)),
        "salary": desc(func.coalesce(JobPosting.salary_max, 0)),
        "urgency": desc(JobPosting.hiring_urgency),
    }
    stmt = stmt.order_by(sort_map.get(sort, sort_map["score"]))
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(stmt.limit(limit).offset(offset)).scalars().all()
    return {"total": total, "items": [_job_row(r) for r in rows]}


@router.get("/jobs/facets")
def job_facets(db: Session = Depends(get_db)):
    def distinct(col):
        return [r[0] for r in db.execute(select(col).where(col.isnot(None)).distinct()).all() if r[0]]
    return {
        "sources": distinct(JobPosting.source),
        "seniority": distinct(JobPosting.seniority),
        "role_family": distinct(JobPosting.role_family),
        "remote": distinct(JobPosting.remote),
        "country": distinct(JobPosting.country),
        "tier": distinct(Company.tier),
        "band": distinct(JobPosting.salary_band),
        "interview_style": distinct(JobPosting.interview_style),
    }


@router.get("/jobs/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db)):
    j = db.get(JobPosting, job_id)
    if not j:
        raise HTTPException(404, "Job not found")
    co = db.get(Company, j.company_id) if j.company_id else None
    contacts = []
    if j.company_id:
        contacts = [
            {"id": c.id, "name": c.name, "kind": c.kind, "role": c.role,
             "github_handle": c.github_handle, "twitter_handle": c.twitter_handle,
             "website": c.website, "relevance_score": c.relevance_score}
            for c in db.execute(
                select(WarmContact).where(WarmContact.company_id == j.company_id)
                .order_by(desc(WarmContact.relevance_score)).limit(20)
            ).scalars()
        ]
    drafts = [
        {"id": d.id, "kind": d.kind, "subject": d.subject, "status": d.status,
         "created_at": d.created_at.isoformat(), "body_md": d.body_md}
        for d in db.execute(
            select(OutreachDraft).where(OutreachDraft.job_id == job_id)
            .order_by(desc(OutreachDraft.created_at))
        ).scalars()
    ]
    return {
        **_job_row(j),
        "description_md": j.description_md,
        "score_breakdown": json.loads(j.score_breakdown_json or "{}"),
        "company": {
            "id": co.id, "name": co.name, "slug": co.slug, "tier": co.tier,
            "open_role_count": co.open_role_count,
            "hiring_velocity_7d": co.hiring_velocity_7d,
            "hiring_velocity_30d": co.hiring_velocity_30d,
        } if co else None,
        "warm_contacts": contacts,
        "outreach_drafts": drafts,
    }


@router.post("/jobs/rescore")
def rescore(backfill: bool = False, db: Session = Depends(get_db)):
    """Recompute job_score for active rows. Pass `?backfill=true` to first
    re-derive role_family/yoe/relevance/quality from stored titles+descriptions
    (use this after a model upgrade so existing rows pick up the new signals)."""
    n_backfilled = 0
    if backfill:
        from app.services.jobs.ingest import backfill_inferred_fields
        n_backfilled = backfill_inferred_fields(db)
    return {"rescored": scoring.rescore_all(db), "backfilled": n_backfilled}


# ---------- dashboard / trends ----------

@router.get("/dashboard/trends")
def dashboard_trends(db: Session = Depends(get_db)):
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    aggressive = db.execute(
        select(
            Company.id, Company.slug, Company.name, Company.tier,
            Company.hiring_velocity_7d, Company.hiring_velocity_30d, Company.open_role_count,
        ).where(Company.hiring_velocity_7d > 0)
        .order_by(desc(Company.hiring_velocity_7d)).limit(15)
    ).all()

    # Trending titles: only count signal roles (persona-aligned), not QA/support/spam.
    trending_titles = db.execute(
        select(JobPosting.title_normalized, func.count().label("n"))
        .where(
            JobPosting.is_active == True,  # noqa: E712
            JobPosting.is_low_signal == False,  # noqa: E712
            JobPosting.first_seen_at >= week_ago,
            JobPosting.role_family.in_(PERSONA_DEFAULT_ROLE_FAMILIES),
        )
        .group_by(JobPosting.title_normalized)
        .order_by(desc("n")).limit(15)
    ).all()

    low_competition = db.execute(
        select(JobPosting).where(
            JobPosting.is_active == True,  # noqa: E712
            JobPosting.is_low_signal == False,  # noqa: E712
            JobPosting.competition_score <= 0.5,
            JobPosting.role_relevance >= 0.6,
            JobPosting.first_seen_at >= month_ago,
        ).order_by(desc(JobPosting.job_score)).limit(15)
    ).scalars().all()

    reposts = db.execute(
        select(JobPosting).where(
            JobPosting.is_active == True,  # noqa: E712
            JobPosting.is_low_signal == False,  # noqa: E712
            JobPosting.repost_count >= 1,
        ).order_by(desc(JobPosting.last_seen_at)).limit(15)
    ).scalars().all()

    # New: high-leverage picks — roles with strong career_leverage in the persona window.
    high_leverage = db.execute(
        select(JobPosting).where(
            JobPosting.is_active == True,  # noqa: E712
            JobPosting.is_low_signal == False,  # noqa: E712
            JobPosting.career_leverage >= 0.65,
            JobPosting.role_relevance >= 0.6,
            JobPosting.first_seen_at >= month_ago,
        ).order_by(desc(JobPosting.career_leverage)).limit(15)
    ).scalars().all()

    profile = db.get(UserJobProfile, 1)
    dream_companies = set(json.loads((profile.target_companies_json if profile else None) or "[]"))
    dream_openings = []
    if dream_companies:
        dream_openings = [
            _job_row(j)
            for j in db.execute(
                select(JobPosting).where(
                    JobPosting.is_active == True,  # noqa: E712
                    JobPosting.is_low_signal == False,  # noqa: E712
                    JobPosting.company_name.in_(dream_companies),
                    JobPosting.first_seen_at >= week_ago,
                ).order_by(desc(JobPosting.job_score)).limit(20)
            ).scalars()
        ]

    return {
        "aggressive_hirers": [
            {"id": c.id, "slug": c.slug, "name": c.name, "tier": c.tier,
             "hiring_velocity_7d": c.hiring_velocity_7d,
             "hiring_velocity_30d": c.hiring_velocity_30d,
             "open_role_count": c.open_role_count}
            for c in aggressive
        ],
        "trending_titles": [{"title": t, "count": n} for t, n in trending_titles if t],
        "low_competition_picks": [_job_row(j) for j in low_competition],
        "high_leverage_picks": [_job_row(j) for j in high_leverage],
        "recent_reposts": [_job_row(j) for j in reposts],
        "dream_company_openings": dream_openings,
    }


# ---------- companies ----------

@router.get("/co")
def list_companies_intel(
    q: str | None = None,
    tier: list[str] | None = Query(default=None),
    sort: str = "velocity",  # velocity|open_roles|name
    limit: int = 200,
    db: Session = Depends(get_db),
):
    stmt = select(Company)
    if q:
        stmt = stmt.where(func.lower(Company.name).like(f"%{q.lower()}%"))
    if tier:
        stmt = stmt.where(Company.tier.in_(tier))
    sort_map = {
        "velocity": desc(Company.hiring_velocity_30d),
        "open_roles": desc(Company.open_role_count),
        "name": Company.name.asc(),
    }
    stmt = stmt.order_by(sort_map.get(sort, sort_map["velocity"])).limit(limit)
    rows = db.execute(stmt).scalars().all()
    return [
        {"id": c.id, "slug": c.slug, "name": c.name, "tier": c.tier,
         "open_role_count": c.open_role_count,
         "hiring_velocity_7d": c.hiring_velocity_7d,
         "hiring_velocity_30d": c.hiring_velocity_30d,
         "careers_url": c.careers_url, "homepage_url": c.homepage_url}
        for c in rows
    ]


@router.get("/co/{slug}")
def get_company(slug: str, db: Session = Depends(get_db)):
    co = db.execute(select(Company).where(Company.slug == slug)).scalar_one_or_none()
    if not co:
        raise HTTPException(404, "Company not found")
    roles = db.execute(
        select(JobPosting).where(
            JobPosting.company_id == co.id,
            JobPosting.is_active == True,  # noqa: E712
            JobPosting.is_low_signal == False,  # noqa: E712
        ).order_by(desc(JobPosting.job_score)).limit(50)
    ).scalars().all()
    news = db.execute(
        select(CompanyNews).where(CompanyNews.company_id == co.id)
        .order_by(desc(CompanyNews.published_at)).limit(10)
    ).scalars().all()
    contacts = db.execute(
        select(WarmContact).where(WarmContact.company_id == co.id)
        .order_by(desc(WarmContact.relevance_score)).limit(50)
    ).scalars().all()
    sources = db.execute(
        select(JobSourceRegistry).where(JobSourceRegistry.company_id == co.id)
    ).scalars().all()
    return {
        "id": co.id, "slug": co.slug, "name": co.name, "tier": co.tier,
        "growth_stage": co.growth_stage, "careers_url": co.careers_url,
        "homepage_url": co.homepage_url, "notes_md": co.notes_md,
        "open_role_count": co.open_role_count,
        "hiring_velocity_7d": co.hiring_velocity_7d,
        "hiring_velocity_30d": co.hiring_velocity_30d,
        "roles": [_job_row(r) for r in roles],
        "news": [{"id": n.id, "headline": n.headline, "url": n.url, "kind": n.kind,
                  "source": n.source, "summary_md": n.summary_md,
                  "published_at": n.published_at.isoformat() if n.published_at else None}
                 for n in news],
        "warm_contacts": [{"id": c.id, "name": c.name, "kind": c.kind, "role": c.role,
                           "github_handle": c.github_handle, "twitter_handle": c.twitter_handle,
                           "website": c.website, "relevance_score": c.relevance_score,
                           "notes_md": c.notes_md, "source_url": c.source_url}
                          for c in contacts],
        "sources": [{"source": s.source, "external_org": s.external_org,
                     "enabled": s.enabled, "last_status": s.last_status,
                     "last_run_at": s.last_run_at.isoformat() if s.last_run_at else None,
                     "last_count": s.last_count}
                    for s in sources],
    }


# ---------- sources ----------

class SourceIn(BaseModel):
    source: str
    external_org: str
    company_name: str | None = None
    enabled: bool = True


@router.get("/sources")
def list_sources(db: Session = Depends(get_db)):
    rows = db.execute(select(JobSourceRegistry)).scalars().all()
    out = []
    for r in rows:
        co = db.get(Company, r.company_id) if r.company_id else None
        out.append({
            "source": r.source, "external_org": r.external_org,
            "enabled": r.enabled, "last_status": r.last_status,
            "last_run_at": r.last_run_at.isoformat() if r.last_run_at else None,
            "last_count": r.last_count,
            "company": {"id": co.id, "slug": co.slug, "name": co.name} if co else None,
        })
    return out


@router.post("/sources")
def add_source(body: SourceIn, db: Session = Depends(get_db)):
    from app.services.jobs.ingest import _ensure_company
    company = _ensure_company(db, body.company_name or body.external_org)
    reg = db.execute(
        select(JobSourceRegistry).where(
            JobSourceRegistry.source == body.source,
            JobSourceRegistry.external_org == body.external_org,
        )
    ).scalar_one_or_none()
    if reg:
        reg.enabled = body.enabled
        reg.company_id = company.id
    else:
        db.add(JobSourceRegistry(
            source=body.source, external_org=body.external_org,
            enabled=body.enabled, company_id=company.id,
        ))
    db.commit()
    return {"ok": True}


@router.delete("/sources/{source}/{org}")
def delete_source(source: str, org: str, db: Session = Depends(get_db)):
    reg = db.execute(
        select(JobSourceRegistry).where(
            JobSourceRegistry.source == source,
            JobSourceRegistry.external_org == org,
        )
    ).scalar_one_or_none()
    if not reg:
        raise HTTPException(404, "Not found")
    db.delete(reg)
    db.commit()
    return {"ok": True}


# ---------- profile ----------

class ProfileIn(BaseModel):
    target_titles: list[str] = []
    target_companies: list[str] = []
    target_min_comp: int | None = None
    target_currency: str = "USD"
    preferred_remote: str | None = None
    preferred_countries: list[str] = []
    needs_visa: bool = False
    stack: list[str] = []
    seniority: str | None = None
    domains: list[str] = []
    weaknesses_md: str | None = None
    resume_md: str | None = None
    github_username: str | None = None
    leetcode_username: str | None = None
    codeforces_handle: str | None = None


def _profile_out(p: UserJobProfile) -> dict:
    return {
        "target_titles": json.loads(p.target_titles_json or "[]"),
        "target_companies": json.loads(p.target_companies_json or "[]"),
        "target_min_comp": p.target_min_comp,
        "target_currency": p.target_currency,
        "preferred_remote": p.preferred_remote,
        "preferred_countries": json.loads(p.preferred_countries_json or "[]"),
        "needs_visa": p.needs_visa,
        "stack": json.loads(p.stack_json or "[]"),
        "seniority": p.seniority,
        "domains": json.loads(p.domains_json or "[]"),
        "weaknesses_md": p.weaknesses_md,
        "resume_md": p.resume_md,
        "github_username": p.github_username,
        "leetcode_username": p.leetcode_username,
        "codeforces_handle": p.codeforces_handle,
        "updated_at": p.updated_at.isoformat(),
    }


@router.get("/profile")
def get_profile(db: Session = Depends(get_db)):
    p = db.get(UserJobProfile, 1)
    if not p:
        p = UserJobProfile(id=1)
        db.add(p)
        db.commit()
        db.refresh(p)
    return _profile_out(p)


@router.put("/profile")
def update_profile(body: ProfileIn, db: Session = Depends(get_db)):
    p = db.get(UserJobProfile, 1)
    if not p:
        p = UserJobProfile(id=1)
        db.add(p)
    p.target_titles_json = json.dumps(body.target_titles)
    p.target_companies_json = json.dumps(body.target_companies)
    p.target_min_comp = body.target_min_comp
    p.target_currency = body.target_currency
    p.preferred_remote = body.preferred_remote
    p.preferred_countries_json = json.dumps(body.preferred_countries)
    p.needs_visa = body.needs_visa
    p.stack_json = json.dumps(body.stack)
    p.seniority = body.seniority
    p.domains_json = json.dumps(body.domains)
    p.weaknesses_md = body.weaknesses_md
    p.resume_md = body.resume_md
    p.github_username = body.github_username
    p.leetcode_username = body.leetcode_username
    p.codeforces_handle = body.codeforces_handle
    p.updated_at = datetime.utcnow()
    db.commit()
    n = scoring.rescore_all(db)
    return {**_profile_out(p), "rescored": n}


# ---------- warm contacts ----------

class WarmContactIn(BaseModel):
    company_id: int
    name: str
    role: str | None = None
    kind: str = "engineer"
    github_handle: str | None = None
    twitter_handle: str | None = None
    website: str | None = None
    public_email: str | None = None
    source_url: str | None = None
    notes_md: str | None = None
    relevance_score: float = 0.5


@router.get("/warm-contacts")
def list_warm(company_id: int | None = None, db: Session = Depends(get_db)):
    stmt = select(WarmContact)
    if company_id:
        stmt = stmt.where(WarmContact.company_id == company_id)
    stmt = stmt.order_by(desc(WarmContact.relevance_score))
    rows = db.execute(stmt).scalars().all()
    return [
        {"id": c.id, "company_id": c.company_id, "name": c.name, "role": c.role,
         "kind": c.kind, "github_handle": c.github_handle,
         "twitter_handle": c.twitter_handle, "website": c.website,
         "public_email": c.public_email, "source_url": c.source_url,
         "notes_md": c.notes_md, "relevance_score": c.relevance_score}
        for c in rows
    ]


@router.post("/warm-contacts")
def add_warm(body: WarmContactIn, db: Session = Depends(get_db)):
    c = WarmContact(**body.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return {"id": c.id}


# ---------- outreach ----------

class OutreachIn(BaseModel):
    kind: str
    body_md: str
    subject: str | None = None
    job_id: str | None = None
    contact_id: int | None = None
    company_id: int | None = None
    generated_by: str = "claude-code"


class OutreachPatch(BaseModel):
    status: str | None = None
    body_md: str | None = None
    subject: str | None = None


@router.get("/outreach")
def list_outreach(
    job_id: str | None = None,
    company_id: int | None = None,
    kind: str | None = None,
    db: Session = Depends(get_db),
):
    stmt = select(OutreachDraft)
    if job_id: stmt = stmt.where(OutreachDraft.job_id == job_id)
    if company_id: stmt = stmt.where(OutreachDraft.company_id == company_id)
    if kind: stmt = stmt.where(OutreachDraft.kind == kind)
    stmt = stmt.order_by(desc(OutreachDraft.created_at))
    rows = db.execute(stmt).scalars().all()
    return [
        {"id": d.id, "kind": d.kind, "subject": d.subject, "body_md": d.body_md,
         "status": d.status, "job_id": d.job_id, "contact_id": d.contact_id,
         "company_id": d.company_id, "generated_by": d.generated_by,
         "created_at": d.created_at.isoformat()}
        for d in rows
    ]


@router.post("/outreach")
def create_outreach(body: OutreachIn, db: Session = Depends(get_db)):
    d = OutreachDraft(**body.model_dump())
    db.add(d)
    db.commit()
    db.refresh(d)
    return {"id": d.id}


@router.patch("/outreach/{draft_id}")
def patch_outreach(draft_id: int, body: OutreachPatch, db: Session = Depends(get_db)):
    d = db.get(OutreachDraft, draft_id)
    if not d:
        raise HTTPException(404, "Not found")
    if body.status is not None: d.status = body.status
    if body.body_md is not None: d.body_md = body.body_md
    if body.subject is not None: d.subject = body.subject
    db.commit()
    return {"ok": True}


# ---------- applications ----------

class ApplicationIn(BaseModel):
    job_id: str
    status: str = "bookmarked"
    applied_via: str | None = None
    contact_id: int | None = None
    notes_md: str | None = None


class ApplicationPatch(BaseModel):
    status: str | None = None
    notes_md: str | None = None
    applied_via: str | None = None


@router.get("/applications")
def list_applications(db: Session = Depends(get_db)):
    rows = db.execute(select(Application).order_by(desc(Application.updated_at))).scalars().all()
    out = []
    for a in rows:
        j = db.get(JobPosting, a.job_id)
        out.append({
            "id": a.id, "job_id": a.job_id, "status": a.status,
            "applied_via": a.applied_via, "contact_id": a.contact_id,
            "notes_md": a.notes_md, "updated_at": a.updated_at.isoformat(),
            "job": {"title": j.title, "company_name": j.company_name, "url": j.url,
                    "salary_max": j.salary_max, "salary_currency": j.salary_currency,
                    "job_score": j.job_score} if j else None,
        })
    return out


@router.post("/applications")
def create_application(body: ApplicationIn, db: Session = Depends(get_db)):
    if not db.get(JobPosting, body.job_id):
        raise HTTPException(404, "Job not found")
    a = Application(**body.model_dump())
    db.add(a)
    db.commit()
    db.refresh(a)
    return {"id": a.id}


@router.patch("/applications/{app_id}")
def patch_application(app_id: int, body: ApplicationPatch, db: Session = Depends(get_db)):
    a = db.get(Application, app_id)
    if not a:
        raise HTTPException(404, "Not found")
    if body.status is not None: a.status = body.status
    if body.notes_md is not None: a.notes_md = body.notes_md
    if body.applied_via is not None: a.applied_via = body.applied_via
    a.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True}

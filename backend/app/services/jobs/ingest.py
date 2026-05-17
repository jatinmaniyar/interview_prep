"""Pull from providers, normalize, dedup, upsert.

Idempotent: re-running updates last_seen_at, repost_count, and any changed
fields. Inactive jobs (not seen this run) flip is_active=False.

Persona-aware: low-signal rows (intern/QA/support/staffing) are still ingested
(so we can audit what's out there) but flagged is_low_signal=True so the API
hides them by default.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Company, JobPosting, JobSourceRegistry
from app.services.jobs import _normalize as N
from app.services.jobs import tagging
from app.services.jobs.providers import PROVIDERS

log = logging.getLogger(__name__)


@dataclass
class IngestResult:
    source: str
    org: str
    fetched: int = 0
    upserted: int = 0
    new: int = 0
    deactivated: int = 0
    low_signal: int = 0
    errors: list[str] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


def _ensure_company(db: Session, name: str, slug: str | None = None) -> Company:
    slug = slug or N.slugify(name)
    co = db.execute(select(Company).where(Company.slug == slug)).scalar_one_or_none()
    if co:
        return co
    co = Company(slug=slug, name=name, tier=tagging.infer_tier(slug))
    db.add(co)
    db.flush()
    return co


def _normalize_raw(raw: dict, company_name: str, company_slug: str | None) -> dict:
    description_text = N.html_to_text(raw.get("description_html"))
    title = raw["title"].strip()
    stack = N.extract_stack(title + " " + description_text)
    location = raw.get("location")
    workplace = raw.get("workplace") or raw.get("commitment")
    remote = N.infer_remote(location, description_text, workplace)
    salary_min = raw.get("salary_min")
    salary_max = raw.get("salary_max")
    currency = raw.get("salary_currency")
    if not salary_max:
        salary_min, salary_max, currency = N.parse_salary_range(description_text[:4000])

    yoe_min, yoe_max = N.infer_yoe(description_text)
    seniority = N.infer_seniority(title, description_text, yoe_min)
    role_family = N.infer_role_family(title, description_text)
    low_signal = N.is_low_signal(title, company_name, description_text, role_family)
    has_sd = N.has_system_design_signal(description_text)

    return {
        "title": title,
        "title_normalized": N.normalize_title(title),
        "company_name": company_name,
        "seniority": seniority,
        "role_family": role_family,
        "yoe_min": yoe_min,
        "yoe_max": yoe_max,
        "is_low_signal": low_signal,
        "has_system_design": has_sd,
        "location": location,
        "remote": remote,
        "country": N.infer_country(location),
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_currency": currency,
        "salary_band": N.salary_band(salary_max, currency),
        "visa_sponsorship": N.infer_visa(description_text),
        "stack_json": json.dumps(stack),
        "description_md": description_text[:8000] or None,
        "url": raw.get("url"),
        "posted_at": raw.get("posted_at"),
        "interview_style": N.infer_interview_style(description_text),
        "dedup_hash": N.dedup_hash(company_name, title, location),
    }


def _upsert_job(db: Session, raw: dict, company: Company, run_started: datetime) -> tuple[JobPosting, bool]:
    norm = _normalize_raw(raw, company.name, company.slug)
    pk = f"{raw['source']}:{raw['external_id']}"
    existing = db.get(JobPosting, pk)
    is_new = existing is None

    # cross-source dedup
    dup_target_id = None
    if is_new:
        dup_row = db.execute(
            select(JobPosting.id).where(
                JobPosting.dedup_hash == norm["dedup_hash"],
                JobPosting.is_active == True,  # noqa: E712
            ).limit(1)
        ).scalar_one_or_none()
        if dup_row and dup_row != pk:
            dup_target_id = dup_row

    stack_list = json.loads(norm["stack_json"])
    urgency = tagging.hiring_urgency(norm["posted_at"], existing.repost_count if existing else 0)
    competition = tagging.competition_score(company.tier, stack_list, norm["remote"])

    # Persona-relevance scores
    rel = tagging.role_relevance(
        norm["role_family"], norm["seniority"],
        norm["yoe_min"], norm["yoe_max"], norm["is_low_signal"],
    )
    eq = tagging.engineering_quality(
        company.slug, company.tier, stack_list, norm["has_system_design"],
    )
    leverage = tagging.career_leverage(
        company.slug, company.tier, norm["role_family"], norm["seniority"], stack_list,
    )

    if existing:
        prev_active = existing.is_active
        for k, v in norm.items():
            setattr(existing, k, v)
        existing.company_id = company.id
        existing.last_seen_at = run_started
        existing.is_active = True
        existing.hiring_urgency = urgency
        existing.competition_score = competition
        existing.role_relevance = rel
        existing.engineering_quality = eq
        existing.career_leverage = leverage
        existing.raw_json = json.dumps(raw.get("raw") or {})[:64_000]
        if not prev_active:
            existing.repost_count += 1
            existing.first_seen_at = run_started
            existing.hiring_urgency = min(1.0, urgency + 0.1)
        return existing, False

    job = JobPosting(
        id=pk,
        source=raw["source"],
        external_id=str(raw["external_id"]),
        company_id=company.id,
        first_seen_at=run_started,
        last_seen_at=run_started,
        is_active=True,
        hiring_urgency=urgency,
        competition_score=competition,
        role_relevance=rel,
        engineering_quality=eq,
        career_leverage=leverage,
        duplicate_of=dup_target_id,
        raw_json=json.dumps(raw.get("raw") or {})[:64_000],
        **norm,
    )
    db.add(job)
    return job, True


def ingest_source(db: Session, source: str, external_org: str, company_name: str | None = None) -> IngestResult:
    if source not in PROVIDERS:
        return IngestResult(source, external_org, errors=[f"unknown source '{source}'"])
    fetch = PROVIDERS[source]
    res = IngestResult(source, external_org)
    run_started = datetime.utcnow()

    reg = db.execute(
        select(JobSourceRegistry).where(
            JobSourceRegistry.source == source,
            JobSourceRegistry.external_org == external_org,
        )
    ).scalar_one_or_none()
    co_name = company_name or (reg and reg.company_id and db.get(Company, reg.company_id).name) or external_org
    company = _ensure_company(db, co_name)

    if not reg:
        reg = JobSourceRegistry(source=source, external_org=external_org, company_id=company.id)
        db.add(reg)
    else:
        reg.company_id = company.id

    seen_ids: set[str] = set()
    try:
        raws: Iterable[dict] = fetch(external_org)
        for raw in raws:
            try:
                raw["company_name"] = raw.get("company_name") or co_name
                job, is_new = _upsert_job(db, raw, company, run_started)
                seen_ids.add(job.id)
                res.upserted += 1
                res.fetched += 1
                if is_new:
                    res.new += 1
                if job.is_low_signal:
                    res.low_signal += 1
            except Exception as e:
                res.errors.append(f"{raw.get('external_id')}: {e}")
    except Exception as e:  # fetch is a generator; errors surface on iteration
        reg.last_status = f"error: {type(e).__name__}"
        reg.last_run_at = run_started
        db.commit()
        res.errors.append(str(e))
        return res

    # deactivate stale jobs from this (source, company) combo
    stale = db.execute(
        select(JobPosting).where(
            JobPosting.source == source,
            JobPosting.company_id == company.id,
            JobPosting.is_active == True,  # noqa: E712
            JobPosting.last_seen_at < run_started,
        )
    ).scalars().all()
    for j in stale:
        if j.id not in seen_ids:
            j.is_active = False
            res.deactivated += 1

    # refresh company stats — only count signal roles to avoid recruiter spam noise
    company.last_seen_at = run_started
    company.open_role_count = sum(1 for _ in db.execute(
        select(JobPosting).where(
            JobPosting.company_id == company.id,
            JobPosting.is_active == True,  # noqa: E712
            JobPosting.is_low_signal == False,  # noqa: E712
        )
    ).scalars())
    from datetime import timedelta
    fresh_30 = sum(1 for _ in db.execute(
        select(JobPosting).where(
            JobPosting.company_id == company.id,
            JobPosting.is_active == True,  # noqa: E712
            JobPosting.is_low_signal == False,  # noqa: E712
            JobPosting.first_seen_at >= run_started - timedelta(days=30),
        )
    ).scalars())
    fresh_7 = sum(1 for _ in db.execute(
        select(JobPosting).where(
            JobPosting.company_id == company.id,
            JobPosting.is_active == True,  # noqa: E712
            JobPosting.is_low_signal == False,  # noqa: E712
            JobPosting.first_seen_at >= run_started - timedelta(days=7),
        )
    ).scalars())
    company.hiring_velocity_30d = fresh_30
    company.hiring_velocity_7d = fresh_7

    reg.last_run_at = run_started
    reg.last_status = "ok"
    reg.last_count = res.fetched
    db.commit()
    return res


def ingest_all_enabled(db: Session) -> list[IngestResult]:
    regs = db.execute(select(JobSourceRegistry).where(JobSourceRegistry.enabled == True)).scalars().all()  # noqa: E712
    out: list[IngestResult] = []
    for r in regs:
        out.append(ingest_source(db, r.source, r.external_org))
    return out


def backfill_inferred_fields(db: Session) -> int:
    """Re-derive role_family / yoe / low_signal / quality scores for existing rows.

    Useful after a model/migration upgrade: avoids a full re-fetch by deriving
    fields from the already-stored title + description_md.
    """
    rows = db.execute(select(JobPosting)).scalars().all()
    n = 0
    for j in rows:
        company = db.get(Company, j.company_id) if j.company_id else None
        company_slug = company.slug if company else None
        company_tier = company.tier if company else None

        desc = j.description_md or ""
        yoe_min, yoe_max = N.infer_yoe(desc)
        role_family = N.infer_role_family(j.title, desc)
        seniority = N.infer_seniority(j.title, desc, yoe_min) or j.seniority
        low_signal = N.is_low_signal(j.title, j.company_name, desc, role_family)
        has_sd = N.has_system_design_signal(desc)
        stack = json.loads(j.stack_json or "[]")

        j.yoe_min = yoe_min
        j.yoe_max = yoe_max
        j.role_family = role_family
        j.seniority = seniority
        j.is_low_signal = low_signal
        j.has_system_design = has_sd
        j.role_relevance = tagging.role_relevance(role_family, seniority, yoe_min, yoe_max, low_signal)
        j.engineering_quality = tagging.engineering_quality(company_slug, company_tier, stack, has_sd)
        j.career_leverage = tagging.career_leverage(company_slug, company_tier, role_family, seniority, stack)
        n += 1
    db.commit()
    return n

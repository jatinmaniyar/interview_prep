from datetime import datetime

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    DateTime,
    PrimaryKeyConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Problem(Base):
    __tablename__ = "problems"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255), index=True)
    difficulty: Mapped[str] = mapped_column(String(16))
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    description_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    examples_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    constraints_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    topics_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    acceptance_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    boilerplate_python: Mapped[str | None] = mapped_column(Text, nullable=True)
    boilerplate_cpp: Mapped[str | None] = mapped_column(Text, nullable=True)
    test_harness_python: Mapped[str | None] = mapped_column(Text, nullable=True)
    method_signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    scraped_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Solution(Base):
    __tablename__ = "solutions"
    __table_args__ = (PrimaryKeyConstraint("problem_id", "language"),)

    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id"))
    language: Mapped[str] = mapped_column(String(16))
    code: Mapped[str] = mapped_column(Text)
    walkthrough_md: Mapped[str | None] = mapped_column(Text, nullable=True)


class TestCase(Base):
    __tablename__ = "test_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id"), index=True)
    input_json: Mapped[str] = mapped_column(Text)
    expected_output_json: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(16))  # sample|edge|stress|adversarial
    generated_by: Mapped[str] = mapped_column(String(32))
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    validated: Mapped[bool] = mapped_column(Boolean, default=False)


class CompanyTag(Base):
    __tablename__ = "company_tags"
    __table_args__ = (PrimaryKeyConstraint("problem_id", "company", "period"),)

    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id"))
    company: Mapped[str] = mapped_column(String(64), index=True)
    frequency: Mapped[float] = mapped_column(Float, default=0.0)
    period: Mapped[str] = mapped_column(String(16))  # 30d|90d|6m|1y|alltime


class UserProgress(Base):
    __tablename__ = "user_progress"

    problem_id: Mapped[int] = mapped_column(
        ForeignKey("problems.id"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String(16), default="unsolved")
    last_attempted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id"), index=True)
    language: Mapped[str] = mapped_column(String(16))
    code: Mapped[str] = mapped_column(Text)
    passed: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    runtime_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BehavioralExperience(Base):
    __tablename__ = "behavioral_experiences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255))
    body_md: Mapped[str] = mapped_column(Text)
    themes_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class SDProblem(Base):
    __tablename__ = "sd_problems"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    type: Mapped[str] = mapped_column(String(8), index=True)  # hld|lld
    topic: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    difficulty: Mapped[str | None] = mapped_column(String(16), nullable=True)
    summary: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tags_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class SDCompanyTag(Base):
    __tablename__ = "sd_company_tags"
    __table_args__ = (PrimaryKeyConstraint("sd_problem_id", "company"),)

    sd_problem_id: Mapped[int] = mapped_column(ForeignKey("sd_problems.id"))
    company: Mapped[str] = mapped_column(String(64), index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    source: Mapped[str] = mapped_column(String(32), default="seed")


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    tier: Mapped[str | None] = mapped_column(String(32), nullable=True)  # faang|unicorn|startup|enterprise|public
    growth_stage: Mapped[str | None] = mapped_column(String(32), nullable=True)
    careers_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    homepage_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    # signals refreshed by enrichment passes
    hiring_velocity_30d: Mapped[int] = mapped_column(Integer, default=0)
    hiring_velocity_7d: Mapped[int] = mapped_column(Integer, default=0)
    open_role_count: Mapped[int] = mapped_column(Integer, default=0)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class JobSourceRegistry(Base):
    """Per-source-per-company ingestion config. e.g. (greenhouse, stripe)."""
    __tablename__ = "job_sources"
    __table_args__ = (PrimaryKeyConstraint("source", "external_org"),)

    source: Mapped[str] = mapped_column(String(32))  # greenhouse|lever|ashby|jsearch|adzuna|muse
    external_org: Mapped[str] = mapped_column(String(128))  # board token, e.g. "stripe"
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_count: Mapped[int] = mapped_column(Integer, default=0)


class JobPosting(Base):
    __tablename__ = "job_postings"

    id: Mapped[str] = mapped_column(String(160), primary_key=True)  # {source}:{external_id}
    source: Mapped[str] = mapped_column(String(32), index=True)
    external_id: Mapped[str] = mapped_column(String(128))
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True, index=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    title_normalized: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    seniority: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)  # intern|junior|mid|senior|staff|principal|manager
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    remote: Mapped[str | None] = mapped_column(String(16), nullable=True)  # remote|hybrid|onsite
    country: Mapped[str | None] = mapped_column(String(64), nullable=True)
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    salary_band: Mapped[str | None] = mapped_column(String(16), nullable=True)  # low|mid|high|top
    visa_sponsorship: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    stack_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    repost_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    dedup_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    duplicate_of: Mapped[str | None] = mapped_column(ForeignKey("job_postings.id"), nullable=True)
    # tags / heuristics
    interview_style: Mapped[str | None] = mapped_column(String(16), nullable=True)  # dsa|practical|mixed
    hiring_urgency: Mapped[float] = mapped_column(Float, default=0.0)  # 0..1
    competition_score: Mapped[float] = mapped_column(Float, default=0.5)  # 0..1, lower=better
    # persona / relevance signals (added 2026-05)
    role_family: Mapped[str | None] = mapped_column(String(24), nullable=True, index=True)
    yoe_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    yoe_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_low_signal: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    has_system_design: Mapped[bool] = mapped_column(Boolean, default=False)
    role_relevance: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    engineering_quality: Mapped[float] = mapped_column(Float, default=0.0)
    career_leverage: Mapped[float] = mapped_column(Float, default=0.0)
    # scoring (denormalized for cheap sort)
    job_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    score_breakdown_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_summary_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class CompanyNews(Base):
    __tablename__ = "company_news"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    headline: Mapped[str] = mapped_column(String(512))
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    kind: Mapped[str | None] = mapped_column(String(32), nullable=True)  # funding|layoff|hiring|product|other
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    summary_md: Mapped[str | None] = mapped_column(Text, nullable=True)


class WarmContact(Base):
    """Public-signal contacts the user might know or could reach at a company.
    Populated by Claude Code commands, NOT by automated scraping of LinkedIn."""
    __tablename__ = "warm_contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str | None] = mapped_column(String(255), nullable=True)
    kind: Mapped[str] = mapped_column(String(32))  # recruiter|hiring_manager|engineer|recent_joiner|ex_employee
    github_handle: Mapped[str | None] = mapped_column(String(128), nullable=True)
    twitter_handle: Mapped[str | None] = mapped_column(String(128), nullable=True)
    website: Mapped[str | None] = mapped_column(Text, nullable=True)
    public_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)  # where we found them
    notes_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class OutreachDraft(Base):
    __tablename__ = "outreach_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("job_postings.id"), nullable=True, index=True)
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("warm_contacts.id"), nullable=True, index=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(32))  # recruiter_dm|referral_ask|hm_outreach|followup|thank_you
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body_md: Mapped[str] = mapped_column(Text)
    generated_by: Mapped[str] = mapped_column(String(32), default="claude-code")
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft|edited|sent|archived
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("job_postings.id"), index=True)
    status: Mapped[str] = mapped_column(String(24), default="bookmarked")
    # bookmarked|applied|recruiter_screen|onsite|offer|rejected|withdrawn
    applied_via: Mapped[str | None] = mapped_column(String(32), nullable=True)  # referral|cold|recruiter
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("warm_contacts.id"), nullable=True)
    notes_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UserJobProfile(Base):
    """Single-row profile used by the ranking engine."""
    __tablename__ = "user_job_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    target_titles_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_companies_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_min_comp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_currency: Mapped[str] = mapped_column(String(8), default="USD")
    preferred_remote: Mapped[str | None] = mapped_column(String(16), nullable=True)
    preferred_countries_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    needs_visa: Mapped[bool] = mapped_column(Boolean, default=False)
    stack_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    seniority: Mapped[str | None] = mapped_column(String(32), nullable=True)
    domains_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    weaknesses_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    resume_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    github_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    leetcode_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    codeforces_handle: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

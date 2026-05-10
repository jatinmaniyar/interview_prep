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
    title: Mapped[str] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(8))  # hld|lld
    prompt_md: Mapped[str] = mapped_column(Text)
    solution_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)


class JobPosting(Base):
    __tablename__ = "job_postings"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(255))
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    raw_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class SpendLog(Base):
    __tablename__ = "spend_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    component: Mapped[str] = mapped_column(String(64))  # testcase-gen|mock|star
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_write_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_usd: Mapped[float] = mapped_column(Float, default=0.0)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

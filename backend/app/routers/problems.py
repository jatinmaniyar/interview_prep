from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import CompanyTag, Problem, Solution, TestCase, UserProgress

router = APIRouter(tags=["problems"])


@router.get("/problems")
def list_problems(
    company: list[str] | None = Query(default=None),
    difficulty: list[str] | None = Query(default=None),
    status: str | None = None,
    min_freq: float | None = None,
    period: str | None = None,
    limit: int = 200,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = select(Problem)
    if difficulty:
        q = q.where(Problem.difficulty.in_(difficulty))
    if company:
        q = q.join(CompanyTag, CompanyTag.problem_id == Problem.id).where(
            CompanyTag.company.in_(company)
        )
        if min_freq is not None:
            q = q.where(CompanyTag.frequency >= min_freq)
        if period:
            q = q.where(CompanyTag.period == period)
        q = q.distinct()
    q = q.limit(limit).offset(offset)
    rows = db.execute(q).scalars().all()

    progress = {
        p.problem_id: p.status
        for p in db.execute(select(UserProgress)).scalars().all()
    }
    out = []
    for p in rows:
        s = progress.get(p.id, "unsolved")
        if status and s != status:
            continue
        out.append(
            {
                "id": p.id,
                "title": p.title,
                "slug": p.slug,
                "difficulty": p.difficulty,
                "is_premium": p.is_premium,
                "status": s,
            }
        )
    return out


@router.get("/problems/{problem_id}")
def get_problem(problem_id: int, db: Session = Depends(get_db)):
    p = db.get(Problem, problem_id)
    if not p:
        raise HTTPException(404, "Problem not found")

    sols = db.execute(
        select(Solution).where(Solution.problem_id == problem_id)
    ).scalars().all()
    samples = db.execute(
        select(TestCase).where(
            TestCase.problem_id == problem_id, TestCase.category == "sample"
        )
    ).scalars().all()
    test_count = db.execute(
        select(func.count()).select_from(TestCase).where(
            TestCase.problem_id == problem_id
        )
    ).scalar_one()
    progress = db.get(UserProgress, problem_id)

    return {
        "id": p.id,
        "title": p.title,
        "slug": p.slug,
        "difficulty": p.difficulty,
        "is_premium": p.is_premium,
        "description_md": p.description_md,
        "examples_json": p.examples_json,
        "constraints_md": p.constraints_md,
        "topics_json": p.topics_json,
        "boilerplate_python": p.boilerplate_python,
        "boilerplate_cpp": p.boilerplate_cpp,
        "method_signature": p.method_signature,
        "solutions": [
            {
                "language": s.language,
                "code": s.code,
                "walkthrough_md": s.walkthrough_md,
            }
            for s in sols
        ],
        "sample_tests": [
            {
                "id": t.id,
                "input_json": t.input_json,
                "expected_output_json": t.expected_output_json,
            }
            for t in samples
        ],
        "test_count": test_count,
        "status": progress.status if progress else "unsolved",
        "notes_md": progress.notes_md if progress else None,
    }

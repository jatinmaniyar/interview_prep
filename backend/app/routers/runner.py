import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Problem, Submission, TestCase, UserProgress
from app.runner.cpp_runner import cleanup, compile_cpp, run_cpp_binary
from app.runner.python_runner import run_python

router = APIRouter(tags=["runner"])


class RunRequest(BaseModel):
    problem_id: int
    language: str  # python|cpp
    code: str


def _method_name(problem: Problem) -> str:
    # method_signature stores the callable name (e.g., "lengthOfLongestSubstring")
    return problem.method_signature or "solve"


def _execute(language: str, code: str, problem: Problem, tests: list[TestCase]) -> dict:
    method = _method_name(problem)
    results = []
    passed = 0
    total_runtime = 0

    if language == "python":
        for tc in tests:
            args = json.loads(tc.input_json)
            expected = json.loads(tc.expected_output_json)
            r = run_python(code, method, args)
            ok = r["ok"] and r["output"] == expected
            if ok:
                passed += 1
            total_runtime += r["runtime_ms"]
            results.append(
                {
                    "test_id": tc.id,
                    "category": tc.category,
                    "passed": ok,
                    "input": args,
                    "expected": expected,
                    "actual": r["output"],
                    "error": r["error"],
                    "runtime_ms": r["runtime_ms"],
                }
            )
    elif language == "cpp":
        bin_path, build_err, build_dir = compile_cpp(code)
        if build_err:
            return {
                "compile_error": build_err,
                "results": [],
                "passed": 0,
                "total": len(tests),
                "runtime_ms": 0,
            }
        try:
            for tc in tests:
                args = json.loads(tc.input_json)
                expected = json.loads(tc.expected_output_json)
                r = run_cpp_binary(bin_path, args)
                ok = r["ok"] and r["output"] == expected
                if ok:
                    passed += 1
                total_runtime += r["runtime_ms"]
                results.append(
                    {
                        "test_id": tc.id,
                        "category": tc.category,
                        "passed": ok,
                        "input": args,
                        "expected": expected,
                        "actual": r["output"],
                        "error": r["error"],
                        "runtime_ms": r["runtime_ms"],
                    }
                )
        finally:
            cleanup(build_dir)
    else:
        raise HTTPException(400, f"Unsupported language: {language}")

    return {
        "results": results,
        "passed": passed,
        "total": len(tests),
        "runtime_ms": total_runtime,
    }


@router.post("/run")
def run_code(req: RunRequest, db: Session = Depends(get_db)):
    """Run user code against sample tests only."""
    problem = db.get(Problem, req.problem_id)
    if not problem:
        raise HTTPException(404, "Problem not found")
    tests = db.execute(
        select(TestCase).where(
            TestCase.problem_id == req.problem_id, TestCase.category == "sample"
        )
    ).scalars().all()
    return _execute(req.language, req.code, problem, tests)


@router.post("/submit")
def submit_code(req: RunRequest, db: Session = Depends(get_db)):
    """Run user code against the full validated test set; persist submission."""
    problem = db.get(Problem, req.problem_id)
    if not problem:
        raise HTTPException(404, "Problem not found")
    tests = db.execute(
        select(TestCase).where(
            TestCase.problem_id == req.problem_id, TestCase.validated == True  # noqa: E712
        )
    ).scalars().all()
    if not tests:
        raise HTTPException(400, "No validated tests available for this problem")

    outcome = _execute(req.language, req.code, problem, tests)
    sub = Submission(
        problem_id=req.problem_id,
        language=req.language,
        code=req.code,
        passed=outcome["passed"],
        total=outcome["total"],
        runtime_ms=outcome["runtime_ms"],
    )
    db.add(sub)

    progress = db.get(UserProgress, req.problem_id)
    if not progress:
        progress = UserProgress(problem_id=req.problem_id, status="unsolved", attempts=0)
        db.add(progress)
    progress.attempts += 1
    progress.last_attempted_at = datetime.utcnow()
    if outcome["passed"] == outcome["total"] and outcome["total"] > 0:
        progress.status = "solved"
    elif progress.status != "solved":
        progress.status = "attempted"

    db.commit()
    return {"submission_id": sub.id, **outcome}

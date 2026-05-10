import json
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any


def compile_cpp(source: str) -> tuple[Path | None, str | None, Path]:
    """Compile a C++ source. Returns (binary_path, error, build_dir)."""
    build_dir = Path(tempfile.gettempdir()) / "interview_prep" / f"build_{uuid.uuid4().hex}"
    build_dir.mkdir(parents=True, exist_ok=True)
    src_path = build_dir / "main.cpp"
    src_path.write_text(source, encoding="utf-8")
    bin_path = build_dir / ("main.exe" if Path(tempfile.gettempdir()).drive else "main")
    proc = subprocess.run(
        ["g++", "-O2", "-std=c++17", str(src_path), "-o", str(bin_path)],
        capture_output=True,
        timeout=30,
    )
    if proc.returncode != 0:
        return None, proc.stderr.decode("utf-8", errors="replace")[-2000:], build_dir
    return bin_path, None, build_dir


def run_cpp_binary(
    bin_path: Path, args: list[Any], timeout_s: float = 5.0
) -> dict:
    payload = json.dumps({"args": args}).encode("utf-8")
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            [str(bin_path)],
            input=payload,
            capture_output=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "output": None,
            "error": f"Time Limit Exceeded ({timeout_s}s)",
            "runtime_ms": int(timeout_s * 1000),
        }
    runtime_ms = int((time.perf_counter() - started) * 1000)
    if proc.returncode != 0:
        return {
            "ok": False,
            "output": None,
            "error": proc.stderr.decode("utf-8", errors="replace")[-2000:],
            "runtime_ms": runtime_ms,
        }
    try:
        output = json.loads(proc.stdout.decode("utf-8"))
    except json.JSONDecodeError:
        return {
            "ok": False,
            "output": None,
            "error": f"Invalid JSON output: {proc.stdout!r}"[-2000:],
            "runtime_ms": runtime_ms,
        }
    return {"ok": True, "output": output, "error": None, "runtime_ms": runtime_ms}


def cleanup(build_dir: Path) -> None:
    shutil.rmtree(build_dir, ignore_errors=True)

import json
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

PY_HARNESS = """\
import json, sys
{user_code}

if __name__ == "__main__":
    payload = json.loads(sys.stdin.read())
    args = payload["args"]
    sol = Solution()
    method = getattr(sol, "{method}")
    result = method(*args)
    sys.stdout.write(json.dumps(result, default=str))
"""


def run_python(
    user_code: str,
    method: str,
    args: list[Any],
    timeout_s: float = 5.0,
) -> dict:
    """Execute user code against one input. Returns {ok, output, error, runtime_ms}."""
    src = PY_HARNESS.format(user_code=user_code, method=method)
    tmp_dir = Path(tempfile.gettempdir()) / "interview_prep"
    tmp_dir.mkdir(exist_ok=True)
    path = tmp_dir / f"sub_{uuid.uuid4().hex}.py"
    path.write_text(src, encoding="utf-8")

    payload = json.dumps({"args": args}).encode("utf-8")
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            ["python", str(path)],
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
    finally:
        try:
            path.unlink()
        except OSError:
            pass

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

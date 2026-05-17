import json
import re
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any


_VARIANT_SEPARATOR = re.compile(r"(?m)^#{5,}\s*$")


def extract_runnable_solution(code: str, method_name: str | None = None) -> str:
    """Reference solutions are often stored as multiple variants joined by '#####' lines.
    Python evaluates every chunk and the last class redefinition wins — frequently a
    deprecated API (e.g. LeetCode's old Interval objects) that breaks against modern
    List[List[int]] test inputs. Return the first chunk that defines a class and (when
    provided) the named method; fall back to the original code if there's no separator."""
    chunks = _VARIANT_SEPARATOR.split(code)
    if len(chunks) == 1:
        return code
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk or "class " not in chunk:
            continue
        if method_name and not re.search(rf"def\s+{re.escape(method_name)}\s*\(", chunk):
            continue
        return chunk
    return code

PY_HARNESS = """\
from __future__ import annotations
import json, sys, math, heapq, bisect, functools, itertools, operator
from math import inf, ceil, floor, log2, sqrt, gcd
from collections import Counter, defaultdict, deque, OrderedDict
from typing import Optional, List, Dict, Tuple, Set, Any, Union
from functools import cache, lru_cache, reduce, partial, cmp_to_key
from itertools import accumulate, combinations, permutations, product, pairwise

class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next

class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right

{user_code}

if __name__ == "__main__":
    import inspect
    from collections import deque as _dq

    def _to_tree(vals):
        if not vals:
            return None
        root = TreeNode(vals[0])
        q, i = _dq([root]), 1
        while q and i < len(vals):
            node = q.popleft()
            if i < len(vals) and vals[i] is not None:
                node.left = TreeNode(vals[i])
                q.append(node.left)
            i += 1
            if i < len(vals) and vals[i] is not None:
                node.right = TreeNode(vals[i])
                q.append(node.right)
            i += 1
        return root

    def _to_listnode(vals):
        if not vals:
            return None
        head = cur = ListNode(vals[0])
        for v in vals[1:]:
            cur.next = ListNode(v)
            cur = cur.next
        return head

    def _ser(val):
        if isinstance(val, TreeNode):
            result, q = [], _dq([val])
            while q:
                node = q.popleft()
                if node is None:
                    result.append(None)
                else:
                    result.append(node.val)
                    q.append(node.left)
                    q.append(node.right)
            while result and result[-1] is None:
                result.pop()
            return result
        if isinstance(val, ListNode):
            result = []
            while val:
                result.append(val.val)
                val = val.next
            return result
        if isinstance(val, list):
            return [_ser(v) for v in val]
        return val

    def _coerce(arg, hint):
        h = str(hint)
        if "TreeNode" in h and isinstance(arg, list):
            return _to_tree(arg)
        if "ListNode" in h and isinstance(arg, list):
            return _to_listnode(arg)
        return arg

    payload = json.loads(sys.stdin.read())
    args = payload["args"]
    method_name = "{method}"
    if method_name.startswith("__"):
        sys.stderr.write(f"Invalid method name stored for this problem: {{method_name!r}}. "
                         "Update method_signature in the database.\\n")
        sys.exit(1)
    sol = Solution()
    method = getattr(sol, method_name)
    params = list(inspect.signature(method).parameters.values())
    n_expected = len(params)
    if n_expected == 1 and len(args) != 1:
        args = [args]
    coerced = [_coerce(a, p.annotation) for a, p in zip(args, params)]
    result = _ser(method(*coerced))
    sys.stdout.write(json.dumps(result, default=str))
"""


def run_python(
    user_code: str,
    method: str,
    args: list[Any],
    harness: str | None = None,
    timeout_s: float = 5.0,
) -> dict:
    """Execute user code against one input. Returns {ok, output, error, runtime_ms}.

    harness: optional custom harness template stored per-problem. Uses {user_code} and
    {method} as placeholders (simple string replace, no brace-escaping required).
    Defaults to PY_HARNESS when None.
    """
    if harness:
        src = harness.replace("{user_code}", user_code).replace("{method}", method)
    else:
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

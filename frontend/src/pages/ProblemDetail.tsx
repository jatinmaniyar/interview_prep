import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import Editor from "@monaco-editor/react";
import {
  getProblem,
  runCode,
  submitCode,
  type ProblemDetailT,
  type RunResult,
} from "../api";

const DEFAULT_PYTHON = (method: string | null) =>
  `class Solution:
    def ${method ?? "solve"}(self, *args):
        # your code here
        pass
`;

const DEFAULT_CPP = `#include <bits/stdc++.h>
using namespace std;
// JSON parsing for input is left to you; use a library or write a tiny parser.
class Solution {
public:
    // implement the required method here
};
int main() {
    // read JSON args from stdin, dispatch to Solution method, print JSON to stdout
    return 0;
}
`;

export default function ProblemDetail() {
  const { id } = useParams();
  const pid = Number(id);
  const [data, setData] = useState<ProblemDetailT | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [language, setLanguage] = useState<"python" | "cpp">("python");
  const [code, setCode] = useState<string>("");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<RunResult | null>(null);
  const [showSolution, setShowSolution] = useState(false);

  useEffect(() => {
    getProblem(pid)
      .then((d) => {
        setData(d);
        const initial =
          language === "python"
            ? d.boilerplate_python ?? DEFAULT_PYTHON(d.method_signature)
            : d.boilerplate_cpp ?? DEFAULT_CPP;
        setCode(initial);
      })
      .catch((e) => setErr(String(e)));
  }, [pid]);

  useEffect(() => {
    if (!data) return;
    setCode(
      language === "python"
        ? data.boilerplate_python ?? DEFAULT_PYTHON(data.method_signature)
        : data.boilerplate_cpp ?? DEFAULT_CPP
    );
    setResult(null);
  }, [language, data]);

  const referenceSolution = useMemo(() => {
    if (!data) return null;
    return data.solutions.find((s) => s.language === language) ?? null;
  }, [data, language]);

  if (err) return <div className="p-6 text-red-400">{err}</div>;
  if (!data) return <div className="p-6 text-slate-400">Loading…</div>;

  async function onRun() {
    setRunning(true);
    setResult(null);
    try {
      setResult(await runCode(pid, language, code));
    } catch (e) {
      setErr(String(e));
    } finally {
      setRunning(false);
    }
  }

  async function onSubmit() {
    setRunning(true);
    setResult(null);
    try {
      setResult(await submitCode(pid, language, code));
    } catch (e) {
      setErr(String(e));
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="h-full grid grid-cols-2">
      {/* Left: problem statement */}
      <div className="border-r border-slate-800 overflow-auto p-6 prose prose-invert max-w-none">
        <div className="flex items-center gap-3 mb-2">
          <h1 className="text-xl font-bold m-0">
            {data.id}. {data.title}
          </h1>
          <span className={difficultyClasses(data.difficulty)}>{data.difficulty}</span>
          {data.is_premium && (
            <span className="text-xs px-2 py-0.5 rounded bg-amber-700/30 border border-amber-700 text-amber-300">
              Premium
            </span>
          )}
          <span className="text-xs text-slate-500 ml-auto">
            {data.test_count} tests · status: {data.status}
          </span>
        </div>
        {data.description_md ? (
          <div
            className="text-sm leading-relaxed"
            dangerouslySetInnerHTML={{ __html: data.description_md }}
          />
        ) : (
          <p className="text-slate-400">No description scraped yet.</p>
        )}
        {data.constraints_md && (
          <div
            className="text-sm mt-4 border-t border-slate-800 pt-3"
            dangerouslySetInnerHTML={{ __html: data.constraints_md }}
          />
        )}

        <div className="mt-6">
          <button
            onClick={() => setShowSolution((s) => !s)}
            className="text-sm text-slate-400 hover:text-white"
          >
            {showSolution ? "Hide" : "Show"} reference solution
          </button>
          {showSolution && referenceSolution && (
            <pre className="text-xs bg-slate-900 p-3 rounded mt-2 overflow-auto">
              <code>{referenceSolution.code}</code>
            </pre>
          )}
        </div>
      </div>

      {/* Right: editor + results */}
      <div className="flex flex-col">
        <div className="flex items-center gap-2 px-4 py-2 border-b border-slate-800">
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value as "python" | "cpp")}
            className="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-sm"
          >
            <option value="python">Python</option>
            <option value="cpp">C++</option>
          </select>
          <div className="flex-1" />
          <button
            onClick={onRun}
            disabled={running}
            className="px-3 py-1 rounded bg-slate-700 hover:bg-slate-600 text-sm"
          >
            Run
          </button>
          <button
            onClick={onSubmit}
            disabled={running}
            className="px-3 py-1 rounded bg-blue-600 hover:bg-blue-500 text-sm"
          >
            Submit
          </button>
        </div>
        <div className="flex-1 min-h-0">
          <Editor
            height="100%"
            language={language === "cpp" ? "cpp" : "python"}
            theme="vs-dark"
            value={code}
            onChange={(v) => setCode(v ?? "")}
            options={{ minimap: { enabled: false }, fontSize: 13 }}
          />
        </div>
        <ResultsPanel result={result} running={running} />
      </div>
    </div>
  );
}

function difficultyClasses(d: string) {
  const base = "text-xs px-2 py-0.5 rounded border";
  if (d === "Easy") return `${base} text-green-400 border-green-700/50`;
  if (d === "Medium") return `${base} text-yellow-400 border-yellow-700/50`;
  if (d === "Hard") return `${base} text-red-400 border-red-700/50`;
  return `${base} text-slate-300 border-slate-600`;
}

function ResultsPanel({ result, running }: { result: RunResult | null; running: boolean }) {
  if (running)
    return (
      <div className="border-t border-slate-800 p-4 text-slate-400 text-sm h-56 overflow-auto">
        Running…
      </div>
    );
  if (!result)
    return (
      <div className="border-t border-slate-800 p-4 text-slate-500 text-sm h-56 overflow-auto">
        Press Run to test against samples, or Submit to run all validated tests.
      </div>
    );
  if (result.compile_error) {
    return (
      <div className="border-t border-slate-800 p-4 h-56 overflow-auto">
        <div className="text-red-400 text-sm font-semibold">Compile error</div>
        <pre className="text-xs whitespace-pre-wrap">{result.compile_error}</pre>
      </div>
    );
  }
  return (
    <div className="border-t border-slate-800 h-56 overflow-auto">
      <div className="px-4 py-2 text-sm border-b border-slate-800 flex gap-4">
        <span className={result.passed === result.total ? "text-green-400" : "text-red-400"}>
          {result.passed} / {result.total} passed
        </span>
        <span className="text-slate-400">{result.runtime_ms} ms</span>
      </div>
      <div className="text-xs">
        {result.results.map((r) => (
          <div
            key={r.test_id}
            className={`px-4 py-2 border-b border-slate-900 ${
              r.passed ? "bg-green-900/10" : "bg-red-900/10"
            }`}
          >
            <div className="flex gap-3 text-slate-400">
              <span>#{r.test_id}</span>
              <span>{r.category}</span>
              <span className={r.passed ? "text-green-400" : "text-red-400"}>
                {r.passed ? "PASS" : "FAIL"}
              </span>
              <span>{r.runtime_ms}ms</span>
            </div>
            {!r.passed && (
              <div className="mt-1 grid grid-cols-3 gap-2 font-mono text-[11px]">
                <Cell label="input" value={r.input} />
                <Cell label="expected" value={r.expected} />
                <Cell label="actual" value={r.actual} />
              </div>
            )}
            {r.error && (
              <pre className="text-red-400 text-[11px] whitespace-pre-wrap mt-1">
                {r.error}
              </pre>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function Cell({ label, value }: { label: string; value: unknown }) {
  return (
    <div>
      <div className="text-slate-500 uppercase text-[10px]">{label}</div>
      <div className="break-all">{JSON.stringify(value)}</div>
    </div>
  );
}

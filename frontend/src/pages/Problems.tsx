import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { listProblems, type ProblemSummary } from "../api";

const DIFFICULTIES = ["Easy", "Medium", "Hard"];
const STATUSES = ["all", "unsolved", "attempted", "solved"];

export default function Problems() {
  const [rows, setRows] = useState<ProblemSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [company, setCompany] = useState<string>("");
  const [difficulty, setDifficulty] = useState<string[]>([]);
  const [status, setStatus] = useState("all");
  const [period, setPeriod] = useState("");
  const [minFreq, setMinFreq] = useState("");
  const [search, setSearch] = useState("");

  const params = useMemo(() => {
    const p = new URLSearchParams();
    if (company) p.set("company", company);
    difficulty.forEach((d) => p.append("difficulty", d));
    if (status !== "all") p.set("status", status);
    if (period) p.set("period", period);
    if (minFreq) p.set("min_freq", minFreq);
    p.set("limit", "500");
    return p;
  }, [company, difficulty, status, period, minFreq]);

  useEffect(() => {
    setLoading(true);
    setErr(null);
    listProblems(params)
      .then(setRows)
      .catch((e) => setErr(String(e)))
      .finally(() => setLoading(false));
  }, [params]);

  const filtered = useMemo(() => {
    if (!search) return rows;
    const s = search.toLowerCase();
    return rows.filter(
      (r) => r.title.toLowerCase().includes(s) || String(r.id).includes(s)
    );
  }, [rows, search]);

  const toggleDifficulty = (d: string) =>
    setDifficulty((cur) =>
      cur.includes(d) ? cur.filter((x) => x !== d) : [...cur, d]
    );

  return (
    <div className="h-full flex flex-col p-6 gap-4 overflow-auto">
      <div className="flex flex-wrap items-end gap-4">
        <Field label="Company">
          <input
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            placeholder="e.g. Amazon"
            className="bg-slate-900 border border-slate-700 rounded px-2 py-1 w-40"
          />
        </Field>
        <Field label="Difficulty">
          <div className="flex gap-2">
            {DIFFICULTIES.map((d) => (
              <button
                key={d}
                onClick={() => toggleDifficulty(d)}
                className={`px-2 py-1 rounded border text-sm ${
                  difficulty.includes(d)
                    ? "bg-blue-600 border-blue-500"
                    : "bg-slate-900 border-slate-700"
                }`}
              >
                {d}
              </button>
            ))}
          </div>
        </Field>
        <Field label="Status">
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="bg-slate-900 border border-slate-700 rounded px-2 py-1"
          >
            {STATUSES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </Field>
        <Field label="Period">
          <select
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            className="bg-slate-900 border border-slate-700 rounded px-2 py-1"
          >
            <option value="">any</option>
            <option value="30d">30d</option>
            <option value="90d">90d</option>
            <option value="6m">6m</option>
            <option value="1y">1y</option>
            <option value="alltime">alltime</option>
          </select>
        </Field>
        <Field label="Min freq">
          <input
            value={minFreq}
            onChange={(e) => setMinFreq(e.target.value)}
            placeholder="0"
            type="number"
            className="bg-slate-900 border border-slate-700 rounded px-2 py-1 w-20"
          />
        </Field>
        <Field label="Search">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="title or id"
            className="bg-slate-900 border border-slate-700 rounded px-2 py-1 w-56"
          />
        </Field>
      </div>

      {err && <div className="text-red-400">{err}</div>}
      {loading && <div className="text-slate-400">Loading…</div>}

      <table className="w-full text-sm border-collapse">
        <thead className="text-left text-slate-400 border-b border-slate-800">
          <tr>
            <th className="py-2 pr-4">#</th>
            <th className="py-2 pr-4">Title</th>
            <th className="py-2 pr-4">Difficulty</th>
            <th className="py-2 pr-4">Premium</th>
            <th className="py-2 pr-4">Status</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map((r) => (
            <tr key={r.id} className="border-b border-slate-900 hover:bg-slate-900">
              <td className="py-2 pr-4 text-slate-400">{r.id}</td>
              <td className="py-2 pr-4">
                <Link to={`/problems/${r.id}`} className="hover:text-blue-400">
                  {r.title}
                </Link>
              </td>
              <td className={`py-2 pr-4 ${diffColor(r.difficulty)}`}>{r.difficulty}</td>
              <td className="py-2 pr-4">{r.is_premium ? "Yes" : ""}</td>
              <td className="py-2 pr-4">{r.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {!loading && filtered.length === 0 && (
        <div className="text-slate-400">No matches.</div>
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-xs uppercase tracking-wide text-slate-400">
      {label}
      {children}
    </label>
  );
}

function diffColor(d: string) {
  if (d === "Easy") return "text-green-400";
  if (d === "Medium") return "text-yellow-400";
  if (d === "Hard") return "text-red-400";
  return "text-slate-300";
}

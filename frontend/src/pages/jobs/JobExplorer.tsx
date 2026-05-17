import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { JobsAPI, fmtAge, fmtSalary, type Facets, type Job } from "../../jobs/api";

const REMOTE = ["remote", "hybrid", "onsite"];
const SENIORITY = ["mid", "senior", "staff", "junior", "principal", "manager"];
// Persona-priority families first so the user sees them first.
const ROLE_FAMILY = [
  "backend", "fullstack", "platform", "distributed", "infra",
  "api", "product_eng", "devops", "frontend", "ml", "data_eng",
  "security", "mobile",
];
const BAND = ["low", "mid", "high", "top"];
const STYLE = ["dsa", "practical", "mixed"];

export default function JobExplorer() {
  const [sp, setSp] = useSearchParams();
  const [items, setItems] = useState<Job[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [facets, setFacets] = useState<Facets | null>(null);

  useEffect(() => {
    JobsAPI.facets().then(setFacets).catch(() => {});
  }, []);

  const params = useMemo(() => {
    const p = new URLSearchParams(sp);
    if (!p.has("limit")) p.set("limit", "100");
    return p;
  }, [sp]);

  useEffect(() => {
    setLoading(true);
    setErr(null);
    JobsAPI.list(params)
      .then((r) => { setItems(r.items); setTotal(r.total); })
      .catch((e) => setErr(String(e)))
      .finally(() => setLoading(false));
  }, [params.toString()]);

  const setOne = (key: string, value: string) => {
    const p = new URLSearchParams(sp);
    value ? p.set(key, value) : p.delete(key);
    setSp(p, { replace: true });
  };
  const toggleMulti = (key: string, value: string) => {
    const p = new URLSearchParams(sp);
    const all = p.getAll(key);
    p.delete(key);
    const next = all.includes(value) ? all.filter((x) => x !== value) : [...all, value];
    next.forEach((v) => p.append(key, v));
    setSp(p, { replace: true });
  };
  const getMulti = (key: string) => sp.getAll(key);

  // Persona toggle: backend defaults to true. The user can flip it off
  // ("show all") to bypass the SDE-2/Senior backend pre-filter.
  const personaOff = sp.get("persona_default") === "false";
  const lowSignalShown = sp.get("exclude_low_signal") === "false";

  return (
    <div className="h-full flex">
      <aside className="w-72 shrink-0 border-r border-slate-800 p-4 overflow-auto space-y-4 text-sm">
        <Filter label="Search">
          <input value={sp.get("q") || ""}
            onChange={(e) => setOne("q", e.target.value)}
            placeholder="title / company / city"
            className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1" />
        </Filter>

        <div className="rounded border border-slate-700 bg-slate-900/50 p-2 space-y-1.5">
          <Toggle
            label="SDE-2 / Senior persona"
            on={!personaOff}
            onChange={(on) => setOne("persona_default", on ? "" : "false")}
            hint={!personaOff ? "Showing mid/senior + backend/fullstack/platform/distributed/infra/api/product-eng." : "Showing all roles."}
          />
          <Toggle
            label="Hide low-signal roles"
            on={!lowSignalShown}
            onChange={(on) => setOne("exclude_low_signal", on ? "" : "false")}
            hint="Hides intern/QA/support/staffing/IT-admin."
          />
        </div>

        <Pills label="Role family" values={ROLE_FAMILY}
          active={getMulti("role_family")} onToggle={(v) => toggleMulti("role_family", v)} />
        <Pills label="Seniority" values={SENIORITY}
          active={getMulti("seniority")} onToggle={(v) => toggleMulti("seniority", v)} />

        <div className="grid grid-cols-2 gap-2">
          <Filter label="Min YOE">
            <input type="number" min="0" max="20"
              value={sp.get("min_yoe") || ""}
              onChange={(e) => setOne("min_yoe", e.target.value)}
              placeholder="3"
              className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1" />
          </Filter>
          <Filter label="Max YOE">
            <input type="number" min="0" max="20"
              value={sp.get("max_yoe") || ""}
              onChange={(e) => setOne("max_yoe", e.target.value)}
              placeholder="8"
              className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1" />
          </Filter>
        </div>

        <Pills label="Remote" values={REMOTE}
          active={getMulti("remote")} onToggle={(v) => toggleMulti("remote", v)} />
        <Pills label="Tier" values={facets?.tier || ["faang", "unicorn", "public", "startup"]}
          active={getMulti("tier")} onToggle={(v) => toggleMulti("tier", v)} />
        <Pills label="Comp band" values={BAND}
          active={getMulti("band")} onToggle={(v) => toggleMulti("band", v)} />
        <Pills label="Interview" values={STYLE}
          active={getMulti("interview_style")} onToggle={(v) => toggleMulti("interview_style", v)} />
        <Pills label="Source" values={facets?.sources || []}
          active={getMulti("source")} onToggle={(v) => toggleMulti("source", v)} />
        <Pills label="Country" values={facets?.country || []}
          active={getMulti("country")} onToggle={(v) => toggleMulti("country", v)} />

        <Filter label="Min salary (USD)">
          <input type="number" value={sp.get("min_salary") || ""}
            onChange={(e) => setOne("min_salary", e.target.value)}
            className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1" />
        </Filter>
        <Filter label="Min relevance (0–1)">
          <input type="number" step="0.05" min="0" max="1"
            value={sp.get("min_relevance") || ""}
            onChange={(e) => setOne("min_relevance", e.target.value)}
            placeholder="0.7"
            className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1" />
        </Filter>
        <Filter label="Min urgency (0–1)">
          <input type="number" step="0.1" min="0" max="1"
            value={sp.get("min_urgency") || ""}
            onChange={(e) => setOne("min_urgency", e.target.value)}
            className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1" />
        </Filter>
        <Filter label="Posted within (days)">
          <input type="number" value={sp.get("posted_within_days") || ""}
            onChange={(e) => setOne("posted_within_days", e.target.value)}
            placeholder="e.g. 14"
            className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1" />
        </Filter>
        <Filter label="Visa sponsorship">
          <select value={sp.get("visa") || ""} onChange={(e) => setOne("visa", e.target.value)}
            className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1">
            <option value="">any</option>
            <option value="true">yes</option>
            <option value="false">no</option>
          </select>
        </Filter>
        <Filter label="Sort">
          <select value={sp.get("sort") || "score"} onChange={(e) => setOne("sort", e.target.value)}
            className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1">
            <option value="score">JobScore</option>
            <option value="relevance">Role relevance</option>
            <option value="leverage">Career leverage</option>
            <option value="quality">Engineering quality</option>
            <option value="posted">Posted date</option>
            <option value="salary">Salary</option>
            <option value="urgency">Urgency</option>
          </select>
        </Filter>
      </aside>

      <div className="flex-1 overflow-auto p-4">
        <div className="text-xs text-slate-400 mb-2">
          {loading ? "Loading…" : `${total} match${total === 1 ? "" : "es"}`}
          {!personaOff && <span className="ml-2 text-slate-500">(persona filter on)</span>}
        </div>
        {err && <div className="text-red-400 text-sm mb-2">{err}</div>}
        <table className="w-full text-sm">
          <thead className="text-left text-slate-400 border-b border-slate-800">
            <tr>
              <th className="py-2 pr-3">Score</th>
              <th className="py-2 pr-3">Rel</th>
              <th className="py-2 pr-3">Title</th>
              <th className="py-2 pr-3">Company</th>
              <th className="py-2 pr-3">Family</th>
              <th className="py-2 pr-3">YOE</th>
              <th className="py-2 pr-3">Remote</th>
              <th className="py-2 pr-3">Salary</th>
              <th className="py-2 pr-3">Seniority</th>
              <th className="py-2 pr-3">Posted</th>
              <th className="py-2 pr-3">Src</th>
            </tr>
          </thead>
          <tbody>
            {items.map((j) => (
              <tr key={j.id} className="border-b border-slate-900 hover:bg-slate-900">
                <td className="py-2 pr-3 text-blue-400">{(j.job_score * 100).toFixed(0)}</td>
                <td className="py-2 pr-3 text-slate-500">{(j.role_relevance * 100).toFixed(0)}</td>
                <td className="py-2 pr-3">
                  <Link to={`/jobs/${encodeURIComponent(j.id)}`} className="hover:text-blue-400">{j.title}</Link>
                  {j.has_system_design && (
                    <span className="ml-2 text-[10px] text-purple-300 border border-purple-700 rounded px-1">
                      sys design
                    </span>
                  )}
                  {j.repost_count > 0 && (
                    <span className="ml-2 text-[10px] text-amber-400 border border-amber-700 rounded px-1">
                      repost ×{j.repost_count}
                    </span>
                  )}
                  {j.is_low_signal && (
                    <span className="ml-2 text-[10px] text-slate-500 border border-slate-700 rounded px-1">
                      low signal
                    </span>
                  )}
                </td>
                <td className="py-2 pr-3 text-slate-300">{j.company_name || "—"}</td>
                <td className="py-2 pr-3 text-slate-400">{j.role_family || "—"}</td>
                <td className="py-2 pr-3 text-slate-400">
                  {j.yoe_min != null ? (j.yoe_max != null && j.yoe_max !== j.yoe_min ? `${j.yoe_min}–${j.yoe_max}` : `${j.yoe_min}+`) : "—"}
                </td>
                <td className="py-2 pr-3 text-slate-400">{j.remote || "—"}</td>
                <td className="py-2 pr-3 text-slate-400">{fmtSalary(j)}</td>
                <td className="py-2 pr-3 text-slate-400">{j.seniority || "—"}</td>
                <td className="py-2 pr-3 text-slate-400">{fmtAge(j.posted_at || j.first_seen_at)}</td>
                <td className="py-2 pr-3 text-slate-500">{j.source}</td>
              </tr>
            ))}
            {!loading && items.length === 0 && (
              <tr><td colSpan={11} className="py-6 text-slate-500">No jobs match. Loosen filters or ingest more sources.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Filter({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <div className="text-[10px] uppercase tracking-wide text-slate-500 mb-1">{label}</div>
      {children}
    </label>
  );
}

function Toggle({ label, on, onChange, hint }:
  { label: string; on: boolean; onChange: (on: boolean) => void; hint?: string }) {
  return (
    <div>
      <label className="flex items-center justify-between gap-2 cursor-pointer">
        <span className="text-xs text-slate-200">{label}</span>
        <button
          type="button"
          onClick={() => onChange(!on)}
          className={`w-9 h-5 rounded-full transition relative ${on ? "bg-blue-600" : "bg-slate-700"}`}>
          <span className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform ${on ? "translate-x-4" : ""}`} />
        </button>
      </label>
      {hint && <div className="text-[10px] text-slate-500 mt-0.5">{hint}</div>}
    </div>
  );
}

function Pills({ label, values, active, onToggle }:
  { label: string; values: string[]; active: string[]; onToggle: (v: string) => void }) {
  if (values.length === 0) return null;
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wide text-slate-500 mb-1">{label}</div>
      <div className="flex flex-wrap gap-1">
        {values.map((v) => (
          <button key={v} onClick={() => onToggle(v)}
            className={`px-2 py-0.5 rounded text-xs border ${
              active.includes(v)
                ? "bg-blue-600 border-blue-500"
                : "bg-slate-900 border-slate-700 hover:border-slate-500"
            }`}>{v}</button>
        ))}
      </div>
    </div>
  );
}

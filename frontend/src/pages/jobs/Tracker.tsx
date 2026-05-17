import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { JobsAPI, type Application } from "../../jobs/api";

const STATUSES = ["bookmarked", "applied", "recruiter_screen", "onsite", "offer", "rejected", "withdrawn"];

export default function Tracker() {
  const [rows, setRows] = useState<Application[]>([]);
  const [err, setErr] = useState<string | null>(null);

  const load = () => { JobsAPI.applications().then(setRows).catch((e) => setErr(String(e))); };
  useEffect(load, []);

  const setStatus = async (id: number, status: string) => {
    await JobsAPI.patchApplication(id, { status });
    load();
  };

  const grouped: Record<string, Application[]> = {};
  for (const s of STATUSES) grouped[s] = [];
  for (const r of rows) (grouped[r.status] || (grouped[r.status] = [])).push(r);

  return (
    <div className="h-full overflow-auto p-6 space-y-6">
      <h1 className="text-xl font-semibold">Application tracker</h1>
      {err && <div className="text-red-400 text-sm">{err}</div>}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {STATUSES.map((s) => (
          <section key={s} className="rounded border border-slate-800 p-3">
            <h2 className="text-xs uppercase tracking-wide text-slate-400 mb-2">
              {s} <span className="text-slate-600">({grouped[s].length})</span>
            </h2>
            <ul className="space-y-2 text-sm">
              {grouped[s].map((a) => (
                <li key={a.id} className="rounded bg-slate-950 border border-slate-800 p-2">
                  <Link to={`/jobs/${encodeURIComponent(a.job_id)}`}
                    className="hover:text-blue-400 font-medium">
                    {a.job?.title || a.job_id}
                  </Link>
                  <div className="text-xs text-slate-400">{a.job?.company_name}</div>
                  <div className="mt-1 flex items-center justify-between">
                    <select value={a.status} onChange={(e) => setStatus(a.id, e.target.value)}
                      className="bg-slate-900 border border-slate-700 rounded text-xs px-1 py-0.5">
                      {STATUSES.map((x) => <option key={x} value={x}>{x}</option>)}
                    </select>
                    <span className="text-[10px] text-slate-500">{a.applied_via || "—"}</span>
                  </div>
                </li>
              ))}
              {grouped[s].length === 0 && <li className="text-slate-600 text-xs">empty</li>}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}

import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { JobsAPI, type CompanyRow } from "../../jobs/api";

export default function CompanyExplorer() {
  const [sp, setSp] = useSearchParams();
  const [rows, setRows] = useState<CompanyRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const params = useMemo(() => new URLSearchParams(sp), [sp]);

  useEffect(() => {
    setLoading(true); setErr(null);
    JobsAPI.companies(params).then(setRows).catch((e) => setErr(String(e))).finally(() => setLoading(false));
  }, [params.toString()]);

  const setOne = (k: string, v: string) => {
    const p = new URLSearchParams(sp);
    v ? p.set(k, v) : p.delete(k);
    setSp(p, { replace: true });
  };

  return (
    <div className="h-full overflow-auto p-6">
      <div className="flex flex-wrap items-end gap-3 mb-4">
        <Field label="Search">
          <input value={sp.get("q") || ""} onChange={(e) => setOne("q", e.target.value)}
            placeholder="company name"
            className="bg-slate-900 border border-slate-700 rounded px-2 py-1 w-64" />
        </Field>
        <Field label="Tier">
          <select value={sp.get("tier") || ""} onChange={(e) => setOne("tier", e.target.value)}
            className="bg-slate-900 border border-slate-700 rounded px-2 py-1">
            <option value="">any</option>
            <option value="faang">faang</option>
            <option value="unicorn">unicorn</option>
            <option value="public">public</option>
            <option value="startup">startup</option>
          </select>
        </Field>
        <Field label="Sort">
          <select value={sp.get("sort") || "velocity"} onChange={(e) => setOne("sort", e.target.value)}
            className="bg-slate-900 border border-slate-700 rounded px-2 py-1">
            <option value="velocity">Hiring velocity</option>
            <option value="open_roles">Open roles</option>
            <option value="name">Name</option>
          </select>
        </Field>
      </div>

      {err && <div className="text-red-400 text-sm mb-2">{err}</div>}
      {loading && <div className="text-slate-400 text-sm">Loading…</div>}

      <table className="w-full text-sm">
        <thead className="text-left text-slate-400 border-b border-slate-800">
          <tr>
            <th className="py-2 pr-4">Company</th>
            <th className="py-2 pr-4">Tier</th>
            <th className="py-2 pr-4">Open roles</th>
            <th className="py-2 pr-4">7d</th>
            <th className="py-2 pr-4">30d</th>
            <th className="py-2 pr-4">Careers</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => (
            <tr key={c.id} className="border-b border-slate-900 hover:bg-slate-900">
              <td className="py-2 pr-4">
                <Link to={`/jobs/companies/${c.slug}`} className="hover:text-blue-400">{c.name}</Link>
              </td>
              <td className="py-2 pr-4 text-slate-400">{c.tier || "—"}</td>
              <td className="py-2 pr-4">{c.open_role_count}</td>
              <td className="py-2 pr-4 text-green-400">+{c.hiring_velocity_7d}</td>
              <td className="py-2 pr-4">{c.hiring_velocity_30d}</td>
              <td className="py-2 pr-4">
                {c.careers_url ? <a className="text-blue-400" href={c.careers_url} target="_blank" rel="noreferrer">↗</a> : "—"}
              </td>
            </tr>
          ))}
          {!loading && rows.length === 0 && (
            <tr><td colSpan={6} className="py-6 text-slate-500">No companies. Run ingestion to populate.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-xs uppercase tracking-wide text-slate-400">
      {label}{children}
    </label>
  );
}

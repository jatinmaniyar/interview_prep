import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { JobsAPI, fmtAge, fmtSalary, type CompanyDetail } from "../../jobs/api";

export default function CompanyDetailPage() {
  const { slug } = useParams();
  const [data, setData] = useState<CompanyDetail | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!slug) return;
    JobsAPI.company(slug).then(setData).catch((e) => setErr(String(e)));
  }, [slug]);

  if (err) return <div className="p-6 text-red-400">{err}</div>;
  if (!data) return <div className="p-6 text-slate-400">Loading…</div>;

  return (
    <div className="h-full overflow-auto p-6 max-w-5xl mx-auto space-y-6">
      <header className="flex items-baseline justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">{data.name}</h1>
          <div className="text-sm text-slate-400">
            {data.tier || "untiered"} · {data.open_role_count} open roles
            {" · "}+{data.hiring_velocity_7d}/7d
            {" · "}{data.hiring_velocity_30d}/30d
          </div>
        </div>
        <div className="text-sm flex gap-3">
          {data.careers_url && <a href={data.careers_url} target="_blank" rel="noreferrer" className="text-blue-400">careers ↗</a>}
          {data.homepage_url && <a href={data.homepage_url} target="_blank" rel="noreferrer" className="text-blue-400">site ↗</a>}
        </div>
      </header>

      {data.sources.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400 mb-2">Ingestion sources</h2>
          <ul className="text-sm space-y-1">
            {data.sources.map((s) => (
              <li key={`${s.source}:${s.external_org}`} className="flex gap-3">
                <span className="text-slate-400">{s.source}</span>
                <span>{s.external_org}</span>
                <span className="text-slate-500">{s.last_status || "—"}</span>
                <span className="text-slate-500">{s.last_count} jobs</span>
                <span className="text-slate-500">{s.last_run_at ? fmtAge(s.last_run_at) : "never"}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {data.news.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400 mb-2">News</h2>
          <ul className="text-sm space-y-1">
            {data.news.map((n) => (
              <li key={n.id}>
                {n.url ? <a href={n.url} target="_blank" rel="noreferrer" className="text-blue-400 hover:underline">{n.headline}</a> : n.headline}
                {n.kind && <span className="ml-2 text-[10px] uppercase text-slate-500">{n.kind}</span>}
                {n.published_at && <span className="ml-2 text-slate-500 text-xs">{fmtAge(n.published_at)}</span>}
              </li>
            ))}
          </ul>
        </section>
      )}

      {data.warm_contacts.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400 mb-2">Warm paths</h2>
          <ul className="text-sm space-y-1">
            {data.warm_contacts.map((c) => (
              <li key={c.id} className="flex flex-wrap gap-2 items-baseline">
                <span className="text-[10px] px-1 border border-slate-700 rounded uppercase">{c.kind}</span>
                <span>{c.name}</span>
                <span className="text-slate-500">{c.role}</span>
                {c.github_handle && <a className="text-blue-400" href={`https://github.com/${c.github_handle}`} target="_blank" rel="noreferrer">gh:{c.github_handle}</a>}
                {c.twitter_handle && <a className="text-blue-400" href={`https://x.com/${c.twitter_handle}`} target="_blank" rel="noreferrer">x:{c.twitter_handle}</a>}
                {c.website && <a className="text-blue-400" href={c.website} target="_blank" rel="noreferrer">site</a>}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400 mb-2">Open roles ({data.roles.length})</h2>
        <table className="w-full text-sm">
          <thead className="text-left text-slate-400 border-b border-slate-800">
            <tr>
              <th className="py-2 pr-3">Score</th>
              <th className="py-2 pr-3">Title</th>
              <th className="py-2 pr-3">Location</th>
              <th className="py-2 pr-3">Remote</th>
              <th className="py-2 pr-3">Salary</th>
              <th className="py-2 pr-3">Posted</th>
            </tr>
          </thead>
          <tbody>
            {data.roles.map((j) => (
              <tr key={j.id} className="border-b border-slate-900 hover:bg-slate-900">
                <td className="py-2 pr-3 text-blue-400">{(j.job_score * 100).toFixed(0)}</td>
                <td className="py-2 pr-3">
                  <Link to={`/jobs/${encodeURIComponent(j.id)}`} className="hover:text-blue-400">{j.title}</Link>
                </td>
                <td className="py-2 pr-3 text-slate-400">{j.location || "—"}</td>
                <td className="py-2 pr-3 text-slate-400">{j.remote || "—"}</td>
                <td className="py-2 pr-3 text-slate-400">{fmtSalary(j)}</td>
                <td className="py-2 pr-3 text-slate-400">{fmtAge(j.posted_at || j.first_seen_at)}</td>
              </tr>
            ))}
            {data.roles.length === 0 && (
              <tr><td colSpan={6} className="py-6 text-slate-500">No active roles.</td></tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { JobsAPI, fmtAge, fmtSalary, type Job, type Trends } from "../../jobs/api";

export default function JobsDashboard() {
  const [trends, setTrends] = useState<Trends | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    JobsAPI.trends().then(setTrends).catch((e) => setErr(String(e)));
  }, []);

  const rescore = async () => {
    setBusy(true);
    try {
      await JobsAPI.rescore();
      setTrends(await JobsAPI.trends());
    } finally { setBusy(false); }
  };

  if (err) return <div className="p-6 text-red-400">{err}</div>;
  if (!trends) return <div className="p-6 text-slate-400">Loading…</div>;

  return (
    <div className="h-full overflow-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Job Intelligence</h1>
        <div className="flex gap-2 text-sm">
          <button onClick={rescore} disabled={busy}
            className="px-3 py-1 rounded border border-slate-700 hover:bg-slate-800">
            {busy ? "Rescoring…" : "Rescore all"}
          </button>
          <Link to="/jobs/profile" className="px-3 py-1 rounded border border-slate-700 hover:bg-slate-800">
            Profile
          </Link>
        </div>
      </div>

      {trends.dream_company_openings.length > 0 && (
        <Section title="Dream company openings (last 7 days)">
          <JobGrid jobs={trends.dream_company_openings} />
        </Section>
      )}

      <Section title="Aggressively hiring right now">
        <table className="w-full text-sm">
          <thead className="text-left text-slate-400 border-b border-slate-800">
            <tr>
              <th className="py-2 pr-4">Company</th>
              <th className="py-2 pr-4">Tier</th>
              <th className="py-2 pr-4">7d</th>
              <th className="py-2 pr-4">30d</th>
              <th className="py-2 pr-4">Open</th>
            </tr>
          </thead>
          <tbody>
            {trends.aggressive_hirers.map((c) => (
              <tr key={c.id} className="border-b border-slate-900 hover:bg-slate-900">
                <td className="py-2 pr-4">
                  <Link to={`/jobs/companies/${c.slug}`} className="hover:text-blue-400">{c.name}</Link>
                </td>
                <td className="py-2 pr-4 text-slate-400">{c.tier || "—"}</td>
                <td className="py-2 pr-4 text-green-400">+{c.hiring_velocity_7d}</td>
                <td className="py-2 pr-4">{c.hiring_velocity_30d}</td>
                <td className="py-2 pr-4">{c.open_role_count}</td>
              </tr>
            ))}
            {trends.aggressive_hirers.length === 0 && (
              <tr><td className="py-3 text-slate-500" colSpan={5}>No recent ingestion data. Run <code>python -m scripts.ingest_jobs --seed</code>.</td></tr>
            )}
          </tbody>
        </table>
      </Section>

      <Section title="Trending titles (last 7 days)">
        <div className="flex flex-wrap gap-2">
          {trends.trending_titles.map((t) => (
            <Link key={t.title} to={`/jobs/explore?q=${encodeURIComponent(t.title)}`}
              className="text-xs px-2 py-1 rounded border border-slate-700 hover:bg-slate-800">
              {t.title} · {t.count}
            </Link>
          ))}
          {trends.trending_titles.length === 0 && <span className="text-slate-500 text-sm">—</span>}
        </div>
      </Section>

      <Section title="High-leverage picks (compounds toward L5/Senior)">
        <JobGrid jobs={trends.high_leverage_picks ?? []} />
      </Section>

      <Section title="Low-competition picks">
        <JobGrid jobs={trends.low_competition_picks} />
      </Section>

      <Section title="Reposted roles (urgency signal)">
        <JobGrid jobs={trends.recent_reposts} />
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400 mb-2">{title}</h2>
      {children}
    </section>
  );
}

function JobGrid({ jobs }: { jobs: Job[] }) {
  if (jobs.length === 0) return <div className="text-sm text-slate-500">—</div>;
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
      {jobs.map((j) => <JobCard key={j.id} job={j} />)}
    </div>
  );
}

function JobCard({ job }: { job: Job }) {
  return (
    <Link to={`/jobs/${encodeURIComponent(job.id)}`}
      className="block rounded border border-slate-800 hover:border-slate-600 p-3 bg-slate-950">
      <div className="flex items-center justify-between gap-2">
        <div className="text-xs text-slate-400">{job.company_name}</div>
        <div className="text-xs text-blue-400">{(job.job_score * 100).toFixed(0)}</div>
      </div>
      <div className="font-medium leading-tight">{job.title}</div>
      <div className="mt-1 flex flex-wrap gap-1 text-[10px]">
        {job.role_family && (
          <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">{job.role_family}</span>
        )}
        {job.seniority && (
          <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">{job.seniority}</span>
        )}
        {job.yoe_min != null && (
          <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">
            {job.yoe_max && job.yoe_max !== job.yoe_min ? `${job.yoe_min}–${job.yoe_max}y` : `${job.yoe_min}+y`}
          </span>
        )}
        {job.has_system_design && (
          <span className="px-1.5 py-0.5 rounded border border-purple-700 text-purple-300">sys design</span>
        )}
      </div>
      <div className="mt-1 text-xs text-slate-400">
        {job.location || "—"} · {job.remote || "—"} · {fmtAge(job.posted_at || job.first_seen_at)}
      </div>
      <div className="mt-1 text-xs text-slate-500 flex justify-between">
        <span>{fmtSalary(job)}</span>
        <span className="text-slate-600">leverage {(job.career_leverage * 100).toFixed(0)}</span>
      </div>
    </Link>
  );
}

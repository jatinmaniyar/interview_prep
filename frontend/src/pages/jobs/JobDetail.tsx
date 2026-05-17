import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { JobsAPI, fmtAge, fmtSalary, type JobDetail } from "../../jobs/api";

export default function JobDetailPage() {
  const { id } = useParams();
  const [data, setData] = useState<JobDetail | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!id) return;
    JobsAPI.detail(decodeURIComponent(id)).then(setData).catch((e) => setErr(String(e)));
  }, [id]);

  const bookmark = async () => {
    if (!data) return;
    setBusy(true);
    try {
      await JobsAPI.createApplication({ job_id: data.id, status: "bookmarked" });
      alert("Bookmarked in tracker.");
    } finally { setBusy(false); }
  };

  if (err) return <div className="p-6 text-red-400">{err}</div>;
  if (!data) return <div className="p-6 text-slate-400">Loading…</div>;

  const breakdown = data.score_breakdown || {};
  const weights = (breakdown as any).weights || {};

  return (
    <div className="h-full overflow-auto p-6 max-w-5xl mx-auto space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-sm text-slate-400">
            {data.company ? (
              <Link to={`/jobs/companies/${data.company.slug}`} className="hover:text-blue-400">
                {data.company.name}
              </Link>
            ) : data.company_name}
            {data.company?.tier && <span className="ml-2 text-slate-500">· {data.company.tier}</span>}
          </div>
          <h1 className="text-2xl font-semibold">{data.title}</h1>
          <div className="mt-1 text-sm text-slate-400">
            {data.location || "—"} · {data.remote || "—"} · {fmtSalary(data)} ·
            {" "}{fmtAge(data.posted_at || data.first_seen_at)} · source: {data.source}
          </div>
          {data.repost_count > 0 && (
            <div className="mt-1 text-xs text-amber-400">Reposted ×{data.repost_count}</div>
          )}
        </div>
        <div className="text-right">
          <div className="text-3xl font-semibold text-blue-400">{(data.job_score * 100).toFixed(0)}</div>
          <div className="text-xs text-slate-500">JobScore</div>
          <div className="mt-2 flex flex-col gap-1">
            {data.url && <a href={data.url} target="_blank" rel="noreferrer"
              className="text-sm px-3 py-1 rounded border border-slate-700 hover:bg-slate-800">Apply ↗</a>}
            <button onClick={bookmark} disabled={busy}
              className="text-sm px-3 py-1 rounded border border-slate-700 hover:bg-slate-800">
              {busy ? "…" : "Bookmark"}
            </button>
          </div>
        </div>
      </div>

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400 mb-2">Score breakdown</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
          {Object.entries(breakdown).filter(([k]) => k !== "weights").map(([k, v]) => (
            <div key={k} className="rounded border border-slate-800 p-2">
              <div className="text-xs text-slate-400">{k.replace(/_/g, " ")}</div>
              <div className="flex items-baseline gap-2">
                <span className="text-base">{((v as number) * 100).toFixed(0)}</span>
                {weights[k] != null && (
                  <span className="text-[10px] text-slate-500">w {weights[k]}</span>
                )}
              </div>
              <div className="h-1 bg-slate-800 mt-1 rounded">
                <div className="h-1 bg-blue-500 rounded" style={{ width: `${(v as number) * 100}%` }} />
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
        <Tag label="Seniority" value={data.seniority} />
        <Tag label="Country" value={data.country} />
        <Tag label="Visa" value={data.visa_sponsorship === null ? "?" :
          data.visa_sponsorship ? "yes" : "no"} />
        <Tag label="Interview" value={data.interview_style || "—"} />
        <Tag label="Comp band" value={data.salary_band || "—"} />
        <Tag label="Urgency" value={`${(data.hiring_urgency * 100).toFixed(0)}%`} />
        <Tag label="Competition" value={`${(data.competition_score * 100).toFixed(0)}%`} />
        <Tag label="Repost" value={String(data.repost_count)} />
      </section>

      {data.stack.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400 mb-2">Stack</h2>
          <div className="flex flex-wrap gap-1">
            {data.stack.map((s) => (
              <span key={s} className="text-xs px-2 py-0.5 border border-slate-700 rounded">{s}</span>
            ))}
          </div>
        </section>
      )}

      {data.ai_summary_md && (
        <section>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400 mb-2">Why this matters</h2>
          <div className="prose prose-invert prose-sm max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{data.ai_summary_md}</ReactMarkdown>
          </div>
        </section>
      )}

      {data.warm_contacts.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400 mb-2">Warm paths</h2>
          <ul className="text-sm space-y-1">
            {data.warm_contacts.map((c) => (
              <li key={c.id} className="flex items-center gap-2">
                <span className="text-[10px] px-1 border border-slate-700 rounded uppercase">{c.kind}</span>
                <span>{c.name}</span>
                <span className="text-slate-500">{c.role}</span>
                {c.github_handle && <a className="text-blue-400" href={`https://github.com/${c.github_handle}`} target="_blank" rel="noreferrer">gh:{c.github_handle}</a>}
                {c.twitter_handle && <a className="text-blue-400" href={`https://x.com/${c.twitter_handle}`} target="_blank" rel="noreferrer">x:{c.twitter_handle}</a>}
              </li>
            ))}
          </ul>
        </section>
      )}

      {data.outreach_drafts.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400 mb-2">Outreach drafts</h2>
          <div className="space-y-2">
            {data.outreach_drafts.map((d) => (
              <details key={d.id} className="rounded border border-slate-800 p-2">
                <summary className="cursor-pointer text-sm">
                  <span className="text-slate-400">{d.kind}</span>
                  {d.subject && <> · <span>{d.subject}</span></>}
                </summary>
                <pre className="mt-2 whitespace-pre-wrap text-sm text-slate-300">{d.body_md}</pre>
              </details>
            ))}
          </div>
        </section>
      )}

      {data.description_md && (
        <section>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400 mb-2">Description</h2>
          <div className="prose prose-invert prose-sm max-w-none whitespace-pre-wrap">
            {data.description_md}
          </div>
        </section>
      )}
    </div>
  );
}

function Tag({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="rounded border border-slate-800 p-2">
      <div className="text-xs text-slate-400">{label}</div>
      <div>{value ?? "—"}</div>
    </div>
  );
}

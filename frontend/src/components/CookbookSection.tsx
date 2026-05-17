// Generic renderer for a single SD-cookbook section.
// Each section's YAML carries a `display` hint; we branch on it here.

export type SectionPayload = {
  section: string;
  title: string;
  display: string;
  description?: string;
  sources?: string[];
  entries?: any[];
  groups?: any[];
};

export default function CookbookSection({ data }: { data: SectionPayload }) {
  return (
    <section
      id={data.section}
      className="scroll-mt-6 pb-12 border-b border-slate-800 last:border-0"
    >
      <h2 className="text-2xl font-bold text-white mb-2">{data.title}</h2>
      {data.description && (
        <p className="text-slate-400 mb-4 max-w-3xl leading-relaxed">
          {data.description}
        </p>
      )}
      <Body data={data} />
      {data.sources && data.sources.length > 0 && (
        <details className="mt-6 text-xs text-slate-500">
          <summary className="cursor-pointer hover:text-slate-300">
            Sources ({data.sources.length})
          </summary>
          <ul className="mt-2 list-disc pl-5 space-y-1">
            {data.sources.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}

function Body({ data }: { data: SectionPayload }) {
  switch (data.display) {
    case "framework":
      return <FrameworkBody entries={data.entries || []} />;
    case "cards":
      return <CardsBody groups={data.groups} entries={data.entries} />;
    case "compare":
      return <CompareBody entries={data.entries || []} />;
    case "numbers":
      return <NumbersBody groups={data.groups || []} />;
    case "sections":
      return <SectionsBody groups={data.groups || []} />;
    default:
      return <pre className="text-xs text-red-400">unknown display: {data.display}</pre>;
  }
}

// -- framework ---------------------------------------------------------------

function FrameworkBody({ entries }: { entries: any[] }) {
  return (
    <ol className="space-y-4">
      {entries.map((e) => (
        <li
          key={e.step}
          className="rounded border border-slate-800 bg-slate-900/40 p-4"
        >
          <div className="flex items-baseline gap-3">
            <span className="text-xs font-mono text-blue-400">Step {e.step}</span>
            <h3 className="text-base font-semibold text-white">{e.title}</h3>
            {e.duration && (
              <span className="text-xs text-slate-500">~{e.duration}</span>
            )}
          </div>
          {e.prompts && (
            <Block label="Prompts to ask">
              <BulletList items={e.prompts} />
            </Block>
          )}
          {e.pitfalls && (
            <Block label="Pitfalls">
              <BulletList items={e.pitfalls} tone="warn" />
            </Block>
          )}
          {e.output && (
            <Block label="Output">
              <p className="text-sm text-slate-300">{e.output}</p>
            </Block>
          )}
        </li>
      ))}
    </ol>
  );
}

// -- cards (grouped or flat) ------------------------------------------------

function CardsBody({ groups, entries }: { groups?: any[]; entries?: any[] }) {
  if (groups) {
    return (
      <div className="space-y-6">
        {groups.map((g) => (
          <div key={g.heading}>
            <h3 className="text-sm uppercase tracking-wide text-slate-400 mb-2">
              {g.heading}
            </h3>
            <CardGrid entries={g.entries || []} />
          </div>
        ))}
      </div>
    );
  }
  return <CardGrid entries={entries || []} />;
}

function CardGrid({ entries }: { entries: any[] }) {
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {entries.map((e) => (
        <div
          key={e.heading}
          className="rounded border border-slate-800 bg-slate-900/40 p-3"
        >
          <div className="flex items-center gap-2">
            <h4 className="text-sm font-semibold text-white">{e.heading}</h4>
            {e.style && (
              <span className="text-xs text-slate-500 italic">{e.style}</span>
            )}
          </div>
          {e.intent && (
            <p className="text-sm text-slate-300 mt-1">{e.intent}</p>
          )}
          {e.bullets && <BulletList items={e.bullets} className="mt-2" />}
          <Meta label="When" value={e.when} />
          <Meta label="Cost" value={e.cost} />
          <Meta label="Flavors" value={e.flavors} />
          <Meta label="Algos" value={e.algos} />
          <Meta label="How" value={e.how} />
          <Meta label="Modern" value={e.modern} />
          <Meta label="Smell" value={e.smell} tone="warn" />
          <Meta label="Fix" value={e.fix} tone="good" />
          <Meta label="Prevent" value={e.prevent} tone="good" />
          <Meta label="Example" value={e.example} />
          <Meta label="Examples" value={e.examples} />
          <Meta label="Watch" value={e.watch} tone="warn" />
        </div>
      ))}
    </div>
  );
}

// -- compare ----------------------------------------------------------------

function CompareBody({ entries }: { entries: any[] }) {
  return (
    <div className="space-y-4">
      {entries.map((e) => (
        <div
          key={e.name}
          className="rounded border border-slate-800 bg-slate-900/40 p-4"
        >
          <h3 className="text-base font-semibold text-white mb-3">{e.name}</h3>
          <div className="grid gap-3 md:grid-cols-2">
            <ComparePane side={e.left} />
            <ComparePane side={e.right} />
          </div>
          {e.extra && (
            <div className="mt-3">
              <ComparePane side={e.extra} />
            </div>
          )}
          {e.pick && (
            <div className="mt-3 text-sm text-emerald-300">
              <span className="text-xs uppercase tracking-wide text-emerald-500 mr-2">
                Pick
              </span>
              {e.pick}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function ComparePane({ side }: { side: { title: string; points: string[] } }) {
  return (
    <div className="rounded bg-slate-950/50 border border-slate-800 p-3">
      <div className="text-sm font-semibold text-slate-100 mb-2">{side.title}</div>
      <BulletList items={side.points} />
    </div>
  );
}

// -- numbers ----------------------------------------------------------------

function NumbersBody({ groups }: { groups: any[] }) {
  return (
    <div className="space-y-6">
      {groups.map((g) => (
        <div key={g.heading}>
          <h3 className="text-sm uppercase tracking-wide text-slate-400 mb-2">
            {g.heading}
          </h3>
          {g.table && <DataTable headers={g.table.headers} rows={g.table.rows} />}
        </div>
      ))}
    </div>
  );
}

function DataTable({ headers, rows }: { headers: string[]; rows: any[][] }) {
  return (
    <div className="overflow-x-auto rounded border border-slate-800">
      <table className="w-full text-sm">
        <thead className="bg-slate-900 text-slate-300">
          <tr>
            {headers.map((h) => (
              <th
                key={h}
                className="text-left px-3 py-2 font-semibold border-b border-slate-800"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr
              key={i}
              className="odd:bg-slate-950/40 even:bg-slate-900/20"
            >
              {r.map((cell, j) => (
                <td
                  key={j}
                  className="px-3 py-1.5 border-b border-slate-900 text-slate-300 font-mono text-xs"
                >
                  {String(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// -- sections (nested headings) --------------------------------------------

function SectionsBody({ groups }: { groups: any[] }) {
  return (
    <div className="space-y-6">
      {groups.map((g) => (
        <div key={g.heading}>
          <h3 className="text-base font-semibold text-slate-100 mb-2">
            {g.heading}
          </h3>
          {g.body && (
            <p className="text-sm text-slate-400 leading-relaxed mb-2 max-w-3xl">
              {g.body}
            </p>
          )}
          <div className="space-y-2">
            {(g.items || []).map((it: any) => (
              <div
                key={it.heading}
                className="rounded border border-slate-800 bg-slate-900/30 p-3"
              >
                <div className="font-semibold text-slate-100 text-sm">
                  {it.heading}
                </div>
                {it.body && (
                  <p className="text-sm text-slate-300 mt-1 leading-relaxed">
                    {it.body}
                  </p>
                )}
                <Meta label="Smell" value={it.smell} tone="warn" />
                <Meta label="Fix" value={it.fix} tone="good" />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// -- shared bits ------------------------------------------------------------

function Block({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mt-3">
      <div className="text-xs uppercase tracking-wide text-slate-500 mb-1">
        {label}
      </div>
      {children}
    </div>
  );
}

function BulletList({
  items,
  tone,
  className = "",
}: {
  items: string[];
  tone?: "warn" | "good";
  className?: string;
}) {
  const color =
    tone === "warn"
      ? "text-amber-300/90"
      : tone === "good"
      ? "text-emerald-300/90"
      : "text-slate-300";
  return (
    <ul className={`list-disc pl-5 text-sm space-y-1 ${color} ${className}`}>
      {items.map((p, i) => (
        <li key={i}>{p}</li>
      ))}
    </ul>
  );
}

function Meta({
  label,
  value,
  tone,
}: {
  label: string;
  value?: string;
  tone?: "warn" | "good";
}) {
  if (!value) return null;
  const color =
    tone === "warn"
      ? "text-amber-300/90"
      : tone === "good"
      ? "text-emerald-300/90"
      : "text-slate-300";
  return (
    <div className="mt-1.5 text-xs">
      <span className="uppercase tracking-wide text-slate-500 mr-2">{label}</span>
      <span className={color}>{value}</span>
    </div>
  );
}

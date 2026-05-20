"use client";
import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { CaseForm } from "@/components/case-form";
import { api } from "@/lib/api";
import type { CaseDetail } from "@/lib/types";

const ACTIONS = [
  { action: "approve", label: "Approve", color: "bg-emerald-600" },
  { action: "needs_info", label: "Needs info", color: "bg-amber-500" },
  { action: "reject", label: "Reject", color: "bg-slate-500" },
  { action: "mark_foia_filed", label: "FOIA filed", color: "bg-violet-600" },
];

export default function CaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [c, setC] = useState<CaseDetail | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.getCase(id)
      .then((d: unknown) => setC(d as CaseDetail))
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : "Failed to load case."));
  }, [id]);

  async function save(patch: Record<string, unknown>) {
    const updated = await api.updateCase(id, patch);
    setC(updated as CaseDetail);
  }

  async function transition(action: string) {
    const updated = await api.transitionCase(id, action);
    setC(updated as CaseDetail);
  }

  if (err) return <AppShell><div className="text-red-600">{err}</div></AppShell>;
  if (!c) return <AppShell><div className="text-slate-500">Loading&hellip;</div></AppShell>;

  return (
    <AppShell>
      <button onClick={() => router.push("/inbox")} className="text-sm text-slate-500 hover:text-slate-900 mb-4">
        &larr; Back to inbox
      </button>

      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2 bg-white rounded-lg border p-6">
          <h1 className="text-xl font-semibold tracking-tight">
            {c.defendant_name}
            {c.defendant_age != null && <span className="text-slate-500 font-normal">, {c.defendant_age}</span>}
          </h1>
          <p className="text-slate-600 text-sm mt-1">
            {[c.county, c.state].filter(Boolean).join(", ")} &middot; {c.sentencing_date}
          </p>
          <p className="mt-2 text-slate-800">{c.sentence_text || "Sentence details pending."}</p>
          {c.summary && <p className="mt-4 text-slate-700">{c.summary}</p>}

          <hr className="my-6" />
          <h2 className="text-sm font-medium text-slate-500 uppercase tracking-wide mb-3">Editable fields</h2>
          <CaseForm c={c} onSave={save} />

          <hr className="my-6" />
          <h2 className="text-sm font-medium text-slate-500 uppercase tracking-wide mb-3">Actions</h2>
          <div className="flex gap-2">
            {ACTIONS.map(a => (
              <button key={a.action} onClick={() => transition(a.action)}
                      className={`text-white text-sm rounded-md px-4 py-1.5 ${a.color}`}>
                {a.label}
              </button>
            ))}
          </div>
        </div>

        <aside className="bg-white rounded-lg border p-6">
          <h2 className="text-sm font-medium text-slate-500 uppercase tracking-wide mb-3">Sources</h2>
          {c.articles.length === 0 && <p className="text-slate-500 text-sm">No articles linked.</p>}
          <ul className="space-y-2 text-sm">
            {c.articles.map(a => (
              <li key={a.id}>
                <a href={a.url} target="_blank" rel="noreferrer"
                   className="text-blue-700 hover:underline line-clamp-2">{a.title || a.url}</a>
                <div className="text-slate-500 text-xs">{a.source_name}</div>
              </li>
            ))}
          </ul>
        </aside>
      </div>
    </AppShell>
  );
}

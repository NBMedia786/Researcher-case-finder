"use client";
import { useEffect, useState, useRef } from "react";
import { useRouter, useParams } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { CaseForm } from "@/components/case-form";
import { api } from "@/lib/api";
import { TEAM_MEMBERS } from "@/lib/types";
import type { CaseDetail } from "@/lib/types";

const ACTIONS: Array<{ action: string; label: string; cls: string; icon: string }> = [
  {
    action: "approve",
    label: "Approve",
    icon: "M5 13l4 4L19 7",
    cls: "bg-emerald-100 text-emerald-700 hover:bg-emerald-200 focus:ring-emerald-500",
  },
  {
    action: "reject",
    label: "Reject",
    icon: "M6 18L18 6M6 6l12 12",
    cls: "bg-rose-100 text-rose-700 hover:bg-rose-200 focus:ring-rose-500",
  },
];

// Distinct color per teammate so they're visually scannable at a glance.
const MEMBER_COLORS: Record<string, { ring: string; bg: string; text: string; chip: string }> = {
  Gagandeep: { ring: "ring-indigo-500",  bg: "bg-indigo-600",  text: "text-indigo-700",  chip: "bg-indigo-100"  },
  Rudransh:  { ring: "ring-emerald-500", bg: "bg-emerald-600", text: "text-emerald-700", chip: "bg-emerald-100" },
  Piyush:    { ring: "ring-amber-500",   bg: "bg-amber-600",   text: "text-amber-700",   chip: "bg-amber-100"   },
  Cyrus:     { ring: "ring-rose-500",    bg: "bg-rose-600",    text: "text-rose-700",    chip: "bg-rose-100"    },
  Shivanshi: { ring: "ring-violet-500",  bg: "bg-violet-600",  text: "text-violet-700",  chip: "bg-violet-100"  },
  Vandana:   { ring: "ring-teal-500",    bg: "bg-teal-600",    text: "text-teal-700",    chip: "bg-teal-100"    },
};

export default function CaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [c, setC] = useState<CaseDetail | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [assignSaving, setAssignSaving] = useState<string | null>(null); // member key being saved
  const [justSaved, setJustSaved] = useState<string | null>(null);
  const autoMarkedRef = useRef(false);

  useEffect(() => {
    api.getCase(id)
      .then((d: unknown) => setC(d as CaseDetail))
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : "Failed to load case."));
  }, [id]);

  // Auto-clear the "New" badge once a researcher opens the case.
  useEffect(() => {
    if (!c || autoMarkedRef.current) return;
    if (c.status === "new") {
      autoMarkedRef.current = true;
      api.updateCase(id, { status: "reviewing" })
        .then((updated) => setC(updated as CaseDetail))
        .catch(() => { /* non-blocking */ });
    }
  }, [c, id]);

  async function save(patch: Record<string, unknown>) {
    const updated = await api.updateCase(id, patch);
    setC(updated as CaseDetail);
  }

  async function assign(name: string | null) {
    const key = name ?? "__unassigned__";
    setAssignSaving(key);
    try {
      await save({ assigned_to: name });
      setJustSaved(key);
      setTimeout(() => setJustSaved((cur) => (cur === key ? null : cur)), 1200);
    } finally {
      setAssignSaving(null);
    }
  }

  async function transition(action: string) {
    const updated = await api.transitionCase(id, action);
    setC(updated as CaseDetail);
  }

  if (err) return <AppShell><div className="text-red-600">{err}</div></AppShell>;
  if (!c) return <AppShell><div className="text-slate-500">Loading&hellip;</div></AppShell>;

  return (
    <AppShell>
      <button
        onClick={() => router.push("/inbox")}
        className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-full bg-slate-100 text-slate-600 hover:bg-slate-200 hover:text-slate-900 transition-all active:scale-95 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-1 mb-4"
      >
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
        Back to inbox
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
          <div className="flex items-baseline justify-between mb-4">
            <h2 className="text-sm font-medium text-slate-500 uppercase tracking-wide">Assign researcher</h2>
            <span className="text-xs text-slate-400">
              {c.assigned_to ? `Assigned to ${c.assigned_to}` : "Unassigned"}
            </span>
          </div>
          <div className="flex flex-wrap items-stretch gap-2.5">
            {/* Unassigned chip */}
            <button
              onClick={() => assign(null)}
              disabled={assignSaving !== null}
              className={
                "group flex items-center gap-2 pl-1.5 pr-3 py-1.5 rounded-full text-sm font-medium transition-all duration-150 " +
                "border focus:outline-none focus:ring-2 focus:ring-offset-1 disabled:opacity-60 disabled:cursor-wait " +
                (c.assigned_to == null
                  ? "bg-slate-900 text-white border-slate-900 shadow-md ring-1 ring-slate-900 focus:ring-slate-700"
                  : "bg-white text-slate-700 border-slate-200 hover:border-slate-400 hover:-translate-y-0.5 hover:shadow-sm focus:ring-slate-400")
              }
            >
              <span className={
                "w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold " +
                (c.assigned_to == null ? "bg-white/15 text-white" : "bg-slate-100 text-slate-400")
              }>
                {assignSaving === "__unassigned__" ? (
                  <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                ) : justSaved === "__unassigned__" ? (
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={3} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728L5.636 5.636m12.728 12.728L18.364 5.636M5.636 18.364l12.728-12.728" />
                  </svg>
                )}
              </span>
              <span>Unassigned</span>
            </button>

            {TEAM_MEMBERS.map((name) => {
              const colors = MEMBER_COLORS[name] || MEMBER_COLORS.Gagandeep;
              const isSelected = c.assigned_to === name;
              const isSaving = assignSaving === name;
              const justFlash = justSaved === name;
              return (
                <button
                  key={name}
                  onClick={() => assign(name)}
                  disabled={assignSaving !== null}
                  className={
                    "group flex items-center gap-2 pl-1.5 pr-3 py-1.5 rounded-full text-sm font-medium transition-all duration-150 " +
                    "border focus:outline-none focus:ring-2 focus:ring-offset-1 disabled:opacity-60 disabled:cursor-wait " +
                    (isSelected
                      ? `${colors.bg} text-white border-transparent shadow-md ring-1 ${colors.ring} focus:ring-slate-400`
                      : `bg-white ${colors.text} border-slate-200 hover:border-slate-300 hover:-translate-y-0.5 hover:shadow-sm focus:ring-slate-400`)
                  }
                >
                  <span className={
                    "w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold " +
                    (isSelected ? "bg-white/20 text-white" : `${colors.chip} ${colors.text}`)
                  }>
                    {isSaving ? (
                      <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                      </svg>
                    ) : justFlash ? (
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={3} viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                    ) : (
                      name.charAt(0)
                    )}
                  </span>
                  <span>{name}</span>
                </button>
              );
            })}
          </div>

          <hr className="my-6" />
          <h2 className="text-sm font-medium text-slate-500 uppercase tracking-wide mb-3">Actions</h2>
          <div className="flex flex-wrap gap-2">
            {ACTIONS.map(a => (
              <button
                key={a.action}
                onClick={() => transition(a.action)}
                className={`inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-full transition-all active:scale-95 focus:outline-none focus:ring-2 focus:ring-offset-1 ${a.cls}`}
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={a.icon} />
                </svg>
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

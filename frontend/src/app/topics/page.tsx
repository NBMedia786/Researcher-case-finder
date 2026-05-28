"use client";

import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { api } from "@/lib/api";
import type { Topic } from "@/lib/types";

// ────────────────────────────────────────────────────────────────────────────
// Templates — pre-built starting points researchers can pick instead of
// staring at an empty form. Each template fills in tested-good keywords +
// AI instructions for that case type.
// ────────────────────────────────────────────────────────────────────────────

interface Template {
  emoji: string;
  name: string;
  description: string;
  keywords: string[];
  criteria: string;
  recency_days: number;
}

const TEMPLATES: Template[] = [
  {
    emoji: "⚖️",
    name: "Homicide Sentencings",
    description: "People sentenced for murder, manslaughter, or related charges",
    keywords: [
      "sentenced murder", "sentenced homicide", "sentence murder",
      "sentence homicide", "sentencing murder", "sentencing homicide",
    ],
    criteria:
      "Find news articles about people who have been sentenced in court for murder, " +
      "homicide, or manslaughter in the United States. The sentencing must have actually " +
      "happened — not just an arrest, trial, or appeal. The case must involve a death " +
      "caused by the defendant's actions.",
    recency_days: 7,
  },
  {
    emoji: "🚸",
    name: "Kidnapping Cases",
    description: "Recent abductions, missing persons, and kidnapping arrests",
    keywords: ["kidnapping", "kidnapped", "abducted", "abduction", "child abduction"],
    criteria:
      "Find news articles about people being kidnapped or abducted in the United States. " +
      "Include cases where a person was forcibly taken, held against their will, or where " +
      "someone has been charged or sentenced for kidnapping. Skip articles about threats, " +
      "fictional accounts, or attempts that were stopped before the abduction.",
    recency_days: 7,
  },
  {
    emoji: "💊",
    name: "Drug Trafficking Convictions",
    description: "Major drug bust convictions and trafficking sentences",
    keywords: [
      "drug trafficking sentenced", "narcotics conviction",
      "fentanyl sentenced", "drug cartel convicted", "drug trafficker sentenced",
    ],
    criteria:
      "Find news articles about people sentenced for drug trafficking, distribution, " +
      "or manufacturing in the United States. The conviction must be for trafficking " +
      "(not simple possession). Include federal and state cases.",
    recency_days: 7,
  },
  {
    emoji: "💼",
    name: "Fraud & White-Collar Crimes",
    description: "Wire fraud, embezzlement, Ponzi schemes, securities fraud",
    keywords: [
      "fraud sentenced", "embezzlement convicted", "wire fraud sentenced",
      "securities fraud sentenced", "Ponzi scheme sentenced",
    ],
    criteria:
      "Find news articles about people sentenced for fraud, embezzlement, wire fraud, " +
      "securities fraud, or other white-collar crimes in the United States. The " +
      "sentencing must have happened. Skip articles about civil settlements or " +
      "regulatory fines without a criminal conviction.",
    recency_days: 14,
  },
  {
    emoji: "👊",
    name: "Domestic Violence Cases",
    description: "Sentencings for domestic abuse, assault, and intimate-partner violence",
    keywords: [
      "domestic violence sentenced", "domestic abuse convicted",
      "intimate partner violence", "spousal abuse sentenced",
    ],
    criteria:
      "Find news articles about people sentenced for domestic violence, domestic " +
      "abuse, or intimate-partner violence in the United States. Include cases where " +
      "the victim was a spouse, partner, or family member. Skip cases involving " +
      "minors as direct victims (covered by child abuse topics).",
    recency_days: 7,
  },
];

const BLANK_TEMPLATE: Template = {
  emoji: "📌",
  name: "",
  description: "",
  keywords: [],
  criteria: "",
  recency_days: 7,
};

// ────────────────────────────────────────────────────────────────────────────
// Helpers
// ────────────────────────────────────────────────────────────────────────────

function relativeTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const days = Math.floor(diffMs / 86400000);
  if (days === 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 30) return `${days}d ago`;
  if (days < 365) return `${Math.floor(days / 30)}mo ago`;
  return `${Math.floor(days / 365)}y ago`;
}

// ────────────────────────────────────────────────────────────────────────────
// Keyword chip input — tag-style entry. Press Enter or comma to add,
// click × to remove. Much friendlier than a comma-separated text field.
// ────────────────────────────────────────────────────────────────────────────

function KeywordChips({
  value,
  onChange,
}: {
  value: string[];
  onChange: (next: string[]) => void;
}) {
  const [draft, setDraft] = useState("");

  function add(raw: string) {
    const cleaned = raw.trim().replace(/,$/, "").trim();
    if (!cleaned) return;
    if (value.includes(cleaned)) return;
    onChange([...value, cleaned]);
    setDraft("");
  }

  function remove(idx: number) {
    onChange(value.filter((_, i) => i !== idx));
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      add(draft);
    } else if (e.key === "Backspace" && !draft && value.length > 0) {
      remove(value.length - 1);
    }
  }

  return (
    <div className="border border-slate-200 rounded-md bg-white px-2 py-2 focus-within:ring-2 focus-within:ring-blue-500 focus-within:border-blue-500 transition">
      <div className="flex flex-wrap gap-1.5">
        {value.map((kw, idx) => (
          <span
            key={`${kw}-${idx}`}
            className="inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full bg-blue-50 text-blue-700 border border-blue-200"
          >
            {kw}
            <button
              type="button"
              onClick={() => remove(idx)}
              aria-label={`Remove ${kw}`}
              className="text-blue-400 hover:text-blue-700 transition"
            >
              <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </span>
        ))}
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
          onBlur={() => add(draft)}
          placeholder={value.length === 0 ? "Type a keyword and press Enter…" : "+ another"}
          className="flex-1 min-w-[140px] outline-none bg-transparent text-sm py-0.5 px-1"
        />
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Topic card — visual card for one topic, replaces the table row.
// ────────────────────────────────────────────────────────────────────────────

function TopicCard({
  topic,
  busy,
  onActivate,
  onEdit,
  onDelete,
}: {
  topic: Topic;
  busy: boolean;
  onActivate: () => void;
  onEdit: () => void;
  onDelete: () => void;
}) {
  return (
    <div
      className={
        "bg-white rounded-2xl border p-5 transition-all " +
        (topic.is_active
          ? "border-emerald-300 ring-2 ring-emerald-100 shadow-sm"
          : "border-slate-200 hover:border-slate-300 hover:shadow-sm")
      }
    >
      <div className="flex items-start justify-between gap-4 mb-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <h3 className="text-base font-semibold text-slate-900">{topic.name}</h3>
            {topic.is_active && (
              <span className="inline-flex items-center gap-1 text-[10px] font-bold tracking-wide px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                ACTIVE
              </span>
            )}
            {topic.is_default && (
              <span className="text-[10px] font-semibold tracking-wide px-2 py-0.5 rounded-full bg-slate-100 text-slate-500">
                default
              </span>
            )}
          </div>
          <div className="flex items-center gap-3 text-xs text-slate-500">
            <span>{topic.case_count} cases</span>
            <span>·</span>
            <span>Last {topic.recency_days}d</span>
            <span>·</span>
            <span>Updated {relativeTime(topic.updated_at)}</span>
          </div>
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          {!topic.is_active && (
            <button
              onClick={onActivate}
              disabled={busy}
              className="inline-flex items-center gap-1 text-xs font-semibold px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 active:scale-95 text-white transition-all disabled:opacity-60 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-1"
            >
              Make active
            </button>
          )}
          <button
            onClick={onEdit}
            disabled={busy}
            className="inline-flex items-center text-xs font-medium px-3 py-1.5 rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200 active:scale-95 transition-all disabled:opacity-60 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-1"
          >
            Edit
          </button>
          {!topic.is_default && !topic.is_active && (
            <button
              onClick={onDelete}
              disabled={busy}
              className="inline-flex items-center text-xs font-medium px-3 py-1.5 rounded-lg text-rose-600 hover:bg-rose-50 active:scale-95 transition-all disabled:opacity-60 focus:outline-none focus:ring-2 focus:ring-rose-500 focus:ring-offset-1"
              aria-label="Delete topic"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6M1 7h22M9 7V4a1 1 0 011-1h4a1 1 0 011 1v3" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {topic.extraction_criteria && (
        <p className="text-sm text-slate-600 mb-3 line-clamp-2">{topic.extraction_criteria}</p>
      )}

      <div className="flex flex-wrap gap-1.5">
        {topic.queries.slice(0, 6).map((q) => (
          <span
            key={q}
            className="inline-flex items-center text-xs px-2 py-0.5 rounded-md bg-slate-100 text-slate-700"
          >
            {q}
          </span>
        ))}
        {topic.queries.length > 6 && (
          <span className="text-xs text-slate-500 self-center">+{topic.queries.length - 6} more</span>
        )}
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Topic editor — friendlier copy + chip input + advanced collapsed by default
// ────────────────────────────────────────────────────────────────────────────

function TopicEditor({
  mode,
  initial,
  busy,
  onSave,
  onCancel,
}: {
  mode: "create" | "edit";
  initial: Template;
  busy: boolean;
  onSave: (data: {
    name: string;
    queries: string[];
    extraction_criteria: string;
    recency_days: number;
  }) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(initial.name);
  const [keywords, setKeywords] = useState<string[]>(initial.keywords);
  const [criteria, setCriteria] = useState(initial.criteria);
  const [recency, setRecency] = useState(initial.recency_days);

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 mb-6">
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-lg font-semibold text-slate-900">
          {mode === "create" ? "Create a new topic" : "Edit topic"}
        </h2>
        <button
          onClick={onCancel}
          disabled={busy}
          className="text-slate-400 hover:text-slate-600 transition"
          aria-label="Close editor"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div className="space-y-5">
        {/* Name */}
        <div>
          <label className="block text-sm font-semibold text-slate-800 mb-1">Topic name</label>
          <p className="text-xs text-slate-500 mb-2">What you&apos;ll call this case type in the inbox.</p>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Kidnapping Cases"
            className="w-full border border-slate-200 rounded-md px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>

        {/* Keywords */}
        <div>
          <label className="block text-sm font-semibold text-slate-800 mb-1">What to search for</label>
          <p className="text-xs text-slate-500 mb-2">
            Keywords or short phrases. Each one is sent as a separate search to every news source.
            Press <kbd className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 text-[10px] font-mono">Enter</kbd> or
            <kbd className="ml-1 px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 text-[10px] font-mono">,</kbd> to add each one.
          </p>
          <KeywordChips value={keywords} onChange={setKeywords} />
        </div>

        {/* Criteria */}
        <div>
          <label className="block text-sm font-semibold text-slate-800 mb-1">
            What counts as a match?
          </label>
          <p className="text-xs text-slate-500 mb-2">
            Describe in plain English what makes an article relevant. The AI uses this to decide
            whether to keep or skip each article it finds.
          </p>
          <textarea
            value={criteria}
            onChange={(e) => setCriteria(e.target.value)}
            rows={5}
            placeholder="e.g. Find news articles about people being kidnapped in the United States. The kidnapping must have actually happened — not threats or fictional accounts."
            className="w-full border border-slate-200 rounded-md px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 leading-relaxed"
          />
        </div>

        {/* Recency */}
        <div>
          <label className="block text-sm font-semibold text-slate-800 mb-1">How fresh?</label>
          <p className="text-xs text-slate-500 mb-2">
            Skip cases where the event happened more than this many days ago.
          </p>
          <div className="flex items-center gap-2">
            <input
              type="number"
              min={1}
              max={365}
              value={recency}
              onChange={(e) =>
                setRecency(Math.max(1, Math.min(365, parseInt(e.target.value, 10) || 1)))
              }
              className="w-24 border border-slate-200 rounded-md px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
            <span className="text-sm text-slate-600">days</span>
            <div className="ml-2 flex items-center gap-1.5">
              {[3, 7, 14, 30].map((d) => (
                <button
                  key={d}
                  type="button"
                  onClick={() => setRecency(d)}
                  className={
                    "text-xs px-2 py-1 rounded-md transition " +
                    (recency === d
                      ? "bg-blue-600 text-white font-semibold"
                      : "bg-slate-100 text-slate-600 hover:bg-slate-200")
                  }
                >
                  {d}d
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 pt-3 border-t border-slate-100">
          <button
            onClick={() =>
              onSave({
                name: name.trim(),
                queries: keywords,
                extraction_criteria: criteria.trim(),
                recency_days: recency,
              })
            }
            disabled={busy || !name.trim() || keywords.length === 0}
            className="inline-flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 active:scale-95 text-white text-sm font-semibold rounded-lg px-5 py-2 transition-all shadow-sm disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
          >
            {busy ? "Saving…" : mode === "create" ? "Create topic" : "Save changes"}
          </button>
          <button
            onClick={onCancel}
            disabled={busy}
            className="inline-flex items-center text-slate-700 text-sm font-medium px-4 py-2 rounded-lg hover:bg-slate-100 transition-all focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2"
          >
            Cancel
          </button>
          {(name.trim() === "" || keywords.length === 0) && (
            <span className="text-xs text-slate-400 ml-auto">
              {name.trim() === "" ? "Name required" : "At least one keyword required"}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Template picker — shown when creating a new topic. Researchers can start
// from a template (much faster) or "start from scratch".
// ────────────────────────────────────────────────────────────────────────────

function TemplatePicker({
  onPick,
  onCancel,
}: {
  onPick: (t: Template) => void;
  onCancel: () => void;
}) {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 mb-6">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Start from a template</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Pre-built starting points. You can tweak everything after.
          </p>
        </div>
        <button
          onClick={onCancel}
          className="text-slate-400 hover:text-slate-600 transition"
          aria-label="Close"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {TEMPLATES.map((t) => (
          <button
            key={t.name}
            onClick={() => onPick(t)}
            className="text-left p-4 rounded-xl border border-slate-200 hover:border-blue-400 hover:bg-blue-50/40 hover:shadow-sm active:scale-[0.99] transition-all focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1"
          >
            <div className="flex items-start gap-3">
              <div className="text-2xl flex-shrink-0">{t.emoji}</div>
              <div className="min-w-0">
                <h3 className="text-sm font-semibold text-slate-900 mb-0.5">{t.name}</h3>
                <p className="text-xs text-slate-500 leading-relaxed">{t.description}</p>
                <div className="mt-2 flex flex-wrap gap-1">
                  {t.keywords.slice(0, 3).map((kw) => (
                    <span
                      key={kw}
                      className="inline-flex items-center text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600"
                    >
                      {kw}
                    </span>
                  ))}
                  {t.keywords.length > 3 && (
                    <span className="text-[10px] text-slate-400 self-center">+{t.keywords.length - 3}</span>
                  )}
                </div>
              </div>
            </div>
          </button>
        ))}

        <button
          onClick={() => onPick(BLANK_TEMPLATE)}
          className="text-left p-4 rounded-xl border border-dashed border-slate-300 hover:border-slate-500 hover:bg-slate-50 active:scale-[0.99] transition-all focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-1"
        >
          <div className="flex items-start gap-3">
            <div className="text-2xl flex-shrink-0">✨</div>
            <div>
              <h3 className="text-sm font-semibold text-slate-900 mb-0.5">Start from scratch</h3>
              <p className="text-xs text-slate-500 leading-relaxed">
                Build your own topic from a blank form.
              </p>
            </div>
          </div>
        </button>
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Main page
// ────────────────────────────────────────────────────────────────────────────

type EditorState =
  | { mode: "closed" }
  | { mode: "picking-template" }
  | { mode: "create"; initial: Template }
  | { mode: "edit"; id: string; initial: Template };

export default function TopicsPage() {
  const [topics, setTopics] = useState<Topic[]>([]);
  const [loading, setLoading] = useState(true);
  const [editor, setEditor] = useState<EditorState>({ mode: "closed" });
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<{ type: "ok" | "err"; msg: string } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = (await api.listTopics()) as { items: Topic[]; total: number };
      r.items.sort((a, b) => {
        if (a.is_active !== b.is_active) return a.is_active ? -1 : 1;
        if (a.is_default !== b.is_default) return a.is_default ? -1 : 1;
        return a.name.localeCompare(b.name);
      });
      setTopics(r.items);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function showToast(type: "ok" | "err", msg: string, ttl = 2800) {
    setToast({ type, msg });
    setTimeout(() => setToast(null), ttl);
  }

  function startNew() {
    setEditor({ mode: "picking-template" });
  }

  function pickTemplate(t: Template) {
    setEditor({ mode: "create", initial: t });
  }

  function startEdit(t: Topic) {
    setEditor({
      mode: "edit",
      id: t.id,
      initial: {
        emoji: t.is_default ? "⚖️" : "📌",
        name: t.name,
        description: "",
        keywords: t.queries,
        criteria: t.extraction_criteria,
        recency_days: t.recency_days,
      },
    });
  }

  function closeEditor() {
    setEditor({ mode: "closed" });
  }

  async function save(data: {
    name: string;
    queries: string[];
    extraction_criteria: string;
    recency_days: number;
  }) {
    if (editor.mode !== "create" && editor.mode !== "edit") return;
    setBusy(true);
    try {
      if (editor.mode === "create") {
        await api.createTopic(data);
        showToast("ok", `Created "${data.name}"`);
      } else {
        await api.updateTopic(editor.id, data);
        showToast("ok", `Saved "${data.name}"`);
      }
      closeEditor();
      load();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "save failed";
      showToast("err", msg.slice(0, 200));
    } finally {
      setBusy(false);
    }
  }

  async function activate(t: Topic) {
    if (t.is_active) return;
    setBusy(true);
    try {
      await api.activateTopic(t.id);
      showToast("ok", `"${t.name}" is now active — next pipeline run uses it`);
      load();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "activate failed";
      showToast("err", msg.slice(0, 200));
    } finally {
      setBusy(false);
    }
  }

  async function remove(t: Topic) {
    if (!confirm(`Delete "${t.name}"? Cases already tagged with it will keep the tag.`)) return;
    setBusy(true);
    try {
      await api.deleteTopic(t.id);
      showToast("ok", `Deleted "${t.name}"`);
      load();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "delete failed";
      showToast("err", msg.slice(0, 200));
    } finally {
      setBusy(false);
    }
  }

  const activeTopic = topics.find((t) => t.is_active) || null;
  const inactiveTopics = topics.filter((t) => !t.is_active);

  return (
    <AppShell>
      {toast && (
        <div
          className={
            "fixed top-20 right-6 max-w-md px-4 py-3 rounded-lg shadow-lg z-50 text-sm font-medium " +
            (toast.type === "ok" ? "bg-emerald-600 text-white" : "bg-red-600 text-white")
          }
        >
          {toast.msg}
        </div>
      )}

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Topics</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Tell the tool what kinds of cases to collect. The active topic decides what the next
            pipeline run goes looking for.
          </p>
        </div>
        {editor.mode === "closed" && (
          <button
            onClick={startNew}
            className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 active:scale-95 text-white text-sm font-semibold rounded-lg px-5 py-2.5 transition-all shadow-md hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
            New topic
          </button>
        )}
      </div>

      {editor.mode === "picking-template" && (
        <TemplatePicker onPick={pickTemplate} onCancel={closeEditor} />
      )}
      {(editor.mode === "create" || editor.mode === "edit") && (
        <TopicEditor
          mode={editor.mode}
          initial={editor.initial}
          busy={busy}
          onSave={save}
          onCancel={closeEditor}
        />
      )}

      {loading ? (
        <div className="text-slate-500 text-sm">Loading topics…</div>
      ) : topics.length === 0 ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center">
          <div className="text-5xl mb-3">🎯</div>
          <h3 className="text-lg font-semibold text-slate-900 mb-1">No topics yet</h3>
          <p className="text-sm text-slate-500 mb-6 max-w-sm mx-auto">
            Create a topic to tell the tool what kinds of cases to collect.
          </p>
          <button
            onClick={startNew}
            className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 active:scale-95 text-white text-sm font-semibold rounded-lg px-5 py-2.5 transition-all shadow-md"
          >
            Create your first topic
          </button>
        </div>
      ) : (
        <div className="space-y-6">
          {activeTopic && (
            <section>
              <h2 className="text-[11px] font-semibold uppercase tracking-widest text-slate-500 mb-3 px-1">
                Currently collecting
              </h2>
              <TopicCard
                topic={activeTopic}
                busy={busy}
                onActivate={() => activate(activeTopic)}
                onEdit={() => startEdit(activeTopic)}
                onDelete={() => remove(activeTopic)}
              />
            </section>
          )}

          {inactiveTopics.length > 0 && (
            <section>
              <h2 className="text-[11px] font-semibold uppercase tracking-widest text-slate-500 mb-3 px-1">
                Other topics ({inactiveTopics.length})
              </h2>
              <div className="space-y-3">
                {inactiveTopics.map((t) => (
                  <TopicCard
                    key={t.id}
                    topic={t}
                    busy={busy}
                    onActivate={() => activate(t)}
                    onEdit={() => startEdit(t)}
                    onDelete={() => remove(t)}
                  />
                ))}
              </div>
            </section>
          )}
        </div>
      )}
    </AppShell>
  );
}

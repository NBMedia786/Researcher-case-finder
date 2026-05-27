"use client";

import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { api } from "@/lib/api";
import type { Topic } from "@/lib/types";

interface DraftTopic {
  name: string;
  queries: string;          // comma-separated in the form
  extraction_criteria: string;
  recency_days: number;
}

const EMPTY_DRAFT: DraftTopic = {
  name: "",
  queries: "",
  extraction_criteria: "",
  recency_days: 7,
};

function queriesToString(qs: string[]): string {
  return qs.join(", ");
}

function stringToQueries(s: string): string[] {
  return s
    .split(",")
    .map((q) => q.trim())
    .filter((q) => q.length > 0);
}

export default function TopicsPage() {
  const [topics, setTopics] = useState<Topic[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<string | "new" | null>(null);
  const [draft, setDraft] = useState<DraftTopic>(EMPTY_DRAFT);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<{ type: "ok" | "err"; msg: string } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = (await api.listTopics()) as { items: Topic[]; total: number };
      // Active first, then default, then by name
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

  function showToast(type: "ok" | "err", msg: string, ttl = 2500) {
    setToast({ type, msg });
    setTimeout(() => setToast(null), ttl);
  }

  function startCreate() {
    setDraft(EMPTY_DRAFT);
    setEditingId("new");
  }

  function startEdit(t: Topic) {
    setDraft({
      name: t.name,
      queries: queriesToString(t.queries),
      extraction_criteria: t.extraction_criteria,
      recency_days: t.recency_days,
    });
    setEditingId(t.id);
  }

  function cancelEdit() {
    setEditingId(null);
    setDraft(EMPTY_DRAFT);
  }

  async function saveDraft() {
    if (!draft.name.trim()) {
      showToast("err", "Name is required");
      return;
    }
    const queries = stringToQueries(draft.queries);
    if (queries.length === 0) {
      showToast("err", "At least one keyword is required");
      return;
    }
    setBusy(true);
    try {
      if (editingId === "new") {
        await api.createTopic({
          name: draft.name.trim(),
          queries,
          extraction_criteria: draft.extraction_criteria.trim(),
          recency_days: draft.recency_days,
        });
        showToast("ok", `Created "${draft.name}"`);
      } else if (editingId) {
        await api.updateTopic(editingId, {
          name: draft.name.trim(),
          queries,
          extraction_criteria: draft.extraction_criteria.trim(),
          recency_days: draft.recency_days,
        });
        showToast("ok", `Saved "${draft.name}"`);
      }
      setEditingId(null);
      setDraft(EMPTY_DRAFT);
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
      showToast("ok", `Activated "${t.name}" — next pipeline run will use it`);
      load();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "activate failed";
      showToast("err", msg.slice(0, 200));
    } finally {
      setBusy(false);
    }
  }

  async function remove(t: Topic) {
    if (!confirm(`Delete topic "${t.name}"? Cases tagged with it will keep the tag but show "(deleted)".`)) {
      return;
    }
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

  return (
    <AppShell>
      {toast && (
        <div
          className={
            "fixed top-20 right-6 max-w-md px-4 py-3 rounded-lg shadow-lg z-50 text-sm " +
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
            Saved search profiles. The active topic drives the next pipeline run.
          </p>
        </div>
        {editingId === null && (
          <button
            onClick={startCreate}
            className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 active:scale-95 text-white text-sm font-semibold rounded-lg px-5 py-2.5 transition-all shadow-md hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            New topic
          </button>
        )}
      </div>

      {editingId !== null && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 mb-6">
          <h2 className="text-lg font-semibold text-slate-900 mb-4">
            {editingId === "new" ? "New topic" : "Edit topic"}
          </h2>
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-600 uppercase tracking-wide mb-1.5">
                Name
              </label>
              <input
                value={draft.name}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                placeholder="e.g. Kidnapping Cases"
                className="w-full border border-slate-200 rounded-md px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 uppercase tracking-wide mb-1.5">
                Keywords (comma-separated)
              </label>
              <input
                value={draft.queries}
                onChange={(e) => setDraft({ ...draft, queries: e.target.value })}
                placeholder="kidnapping, kidnapped, abducted, abduction"
                className="w-full border border-slate-200 rounded-md px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="text-[11px] text-slate-500 mt-1">
                Each keyword/phrase becomes its own search query against every API.
              </p>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 uppercase tracking-wide mb-1.5">
                Match criteria
              </label>
              <textarea
                value={draft.extraction_criteria}
                onChange={(e) => setDraft({ ...draft, extraction_criteria: e.target.value })}
                rows={5}
                placeholder="An article reporting that a person has been forcibly taken or held against their will in the United States. Set is_match=true only when the kidnapping has actually occurred — not threats, attempts disrupted before the abduction, or fictional accounts."
                className="w-full border border-slate-200 rounded-md px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 leading-relaxed"
              />
              <p className="text-[11px] text-slate-500 mt-1">
                Plain English. This goes into the Gemini prompt to decide what counts as a match.
              </p>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 uppercase tracking-wide mb-1.5">
                Recency window (days)
              </label>
              <input
                type="number"
                min={1}
                max={3650}
                value={draft.recency_days}
                onChange={(e) =>
                  setDraft({ ...draft, recency_days: Math.max(1, Math.min(3650, parseInt(e.target.value, 10) || 1)) })
                }
                className="w-32 border border-slate-200 rounded-md px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="text-[11px] text-slate-500 mt-1">
                Drop cases where the relevant event is older than this many days.
              </p>
            </div>
            <div className="flex items-center gap-2 pt-2">
              <button
                onClick={saveDraft}
                disabled={busy}
                className="inline-flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 active:scale-95 text-white text-sm font-semibold rounded-lg px-4 py-2 transition-all shadow-sm disabled:opacity-60 disabled:cursor-wait focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
              >
                {busy ? "Saving…" : editingId === "new" ? "Create topic" : "Save changes"}
              </button>
              <button
                onClick={cancelEdit}
                disabled={busy}
                className="inline-flex items-center gap-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-sm font-medium rounded-lg px-4 py-2 transition-all focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-slate-500 text-sm">Loading topics…</div>
      ) : topics.length === 0 ? (
        <div className="text-slate-500 text-sm">No topics yet. Create one to get started.</div>
      ) : (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="text-left p-3 font-medium">Topic</th>
                <th className="text-left p-3 font-medium">Keywords</th>
                <th className="text-right p-3 font-medium">Recency</th>
                <th className="text-right p-3 font-medium">Cases</th>
                <th className="p-3"></th>
              </tr>
            </thead>
            <tbody>
              {topics.map((t) => (
                <tr key={t.id} className="border-t border-slate-100">
                  <td className="p-3">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-slate-900">{t.name}</span>
                      {t.is_active && (
                        <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700">
                          ACTIVE
                        </span>
                      )}
                      {t.is_default && (
                        <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-slate-100 text-slate-600">
                          default
                        </span>
                      )}
                    </div>
                    {t.extraction_criteria && (
                      <p className="text-xs text-slate-500 mt-1 line-clamp-2">{t.extraction_criteria}</p>
                    )}
                  </td>
                  <td className="p-3 text-slate-600">
                    <div className="flex flex-wrap gap-1 max-w-md">
                      {t.queries.slice(0, 4).map((q) => (
                        <span key={q} className="inline-flex items-center text-xs px-2 py-0.5 rounded-md bg-slate-100 text-slate-700">
                          {q}
                        </span>
                      ))}
                      {t.queries.length > 4 && (
                        <span className="text-xs text-slate-500">+{t.queries.length - 4}</span>
                      )}
                    </div>
                  </td>
                  <td className="p-3 text-right text-slate-700">{t.recency_days}d</td>
                  <td className="p-3 text-right text-slate-700 font-medium">{t.case_count}</td>
                  <td className="p-3 text-right space-x-2 whitespace-nowrap">
                    {!t.is_active && (
                      <button
                        onClick={() => activate(t)}
                        disabled={busy}
                        className="inline-flex items-center text-xs font-medium px-3 py-1 rounded-full bg-emerald-100 text-emerald-700 hover:bg-emerald-200 active:scale-95 transition-all disabled:opacity-60 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-1"
                      >
                        Activate
                      </button>
                    )}
                    <button
                      onClick={() => startEdit(t)}
                      disabled={busy}
                      className="inline-flex items-center text-xs font-medium px-3 py-1 rounded-full bg-slate-100 text-slate-700 hover:bg-slate-200 active:scale-95 transition-all disabled:opacity-60 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-1"
                    >
                      Edit
                    </button>
                    {!t.is_default && !t.is_active && (
                      <button
                        onClick={() => remove(t)}
                        disabled={busy}
                        className="inline-flex items-center text-xs font-medium px-3 py-1 rounded-full bg-rose-100 text-rose-700 hover:bg-rose-200 active:scale-95 transition-all disabled:opacity-60 focus:outline-none focus:ring-2 focus:ring-rose-500 focus:ring-offset-1"
                      >
                        Delete
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </AppShell>
  );
}

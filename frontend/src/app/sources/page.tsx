"use client";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { api } from "@/lib/api";
import { formatIST } from "@/lib/utils";
import type { SourceItem } from "@/lib/types";

function statusOf(s: SourceItem) {
  if (!s.is_active) return { label: "off", color: "bg-slate-300" };
  if (s.consecutive_failures >= 3) return { label: "failing", color: "bg-red-500" };
  if (s.consecutive_failures > 0) return { label: "warn", color: "bg-amber-500" };
  if (!s.last_success_at) return { label: "new", color: "bg-slate-400" };
  return { label: "ok", color: "bg-emerald-500" };
}

export default function SourcesPage() {
  const [items, setItems] = useState<SourceItem[]>([]);
  // Per-row inline-edit state: source id -> { value, saving }
  const [edit, setEdit] = useState<Record<string, { value: string; saving: boolean }>>({});
  const [toast, setToast] = useState<{ type: "ok" | "err"; msg: string } | null>(null);

  async function load() {
    const r = await api.listSources() as { items: SourceItem[] };
    setItems(r.items);
  }
  useEffect(() => { load(); }, []);

  function startEdit(id: string) {
    setEdit((e) => ({ ...e, [id]: { value: "", saving: false } }));
  }
  function cancelEdit(id: string) {
    setEdit((e) => {
      const next = { ...e };
      delete next[id];
      return next;
    });
  }
  async function saveKey(s: SourceItem) {
    if (!s.key_field) return;
    const row = edit[s.id];
    if (!row) return;
    setEdit((e) => ({ ...e, [s.id]: { ...row, saving: true } }));
    try {
      await api.updateSourceConfig(s.id, s.key_field as "api_key" | "api_token", row.value);
      setToast({
        type: "ok",
        msg: row.value.trim()
          ? `✓ Saved API key for ${s.name}`
          : `✓ Cleared API key for ${s.name} — env fallback will be used`,
      });
      cancelEdit(s.id);
      await load();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "save failed";
      setToast({ type: "err", msg: `Failed to save: ${msg.slice(0, 200)}` });
      setEdit((e2) => ({ ...e2, [s.id]: { ...row, saving: false } }));
    } finally {
      setTimeout(() => setToast(null), 4000);
    }
  }

  return (
    <AppShell>
      {toast && (
        <div className={`fixed top-20 right-6 max-w-md px-4 py-3 rounded-lg shadow-lg z-50 text-sm ${
          toast.type === "ok" ? "bg-emerald-600 text-white" : "bg-red-600 text-white"
        }`}>
          {toast.msg}
        </div>
      )}

      <div className="flex items-end justify-between mb-6">
        <h1 className="text-xl font-semibold tracking-tight">Sources</h1>
        <p className="text-xs text-slate-500">
          API keys saved here override any env-var fallback. Clear a key to revert to env.
        </p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600 text-xs uppercase tracking-wider">
            <tr>
              <th className="text-left px-3 py-2.5 w-8"></th>
              <th className="text-left px-3 py-2.5">Name</th>
              <th className="text-left px-3 py-2.5">Type</th>
              <th className="text-left px-3 py-2.5">API key</th>
              <th className="text-right px-3 py-2.5">Fetched</th>
              <th className="text-right px-3 py-2.5">Extracted</th>
              <th className="text-left px-3 py-2.5">Last run (IST)</th>
              <th className="px-3 py-2.5 w-48"></th>
            </tr>
          </thead>
          <tbody>
            {items.map(s => {
              const st = statusOf(s);
              const isEditing = !!edit[s.id];
              const editRow = edit[s.id];
              return (
                <tr key={s.id} className="border-t border-slate-100 hover:bg-slate-50/40 transition">
                  <td className="px-3 py-2.5">
                    <span className={`inline-block w-2.5 h-2.5 rounded-full ${st.color}`} title={st.label} />
                  </td>
                  <td className="px-3 py-2.5 font-medium text-slate-900">
                    {s.homepage_url ? (
                      <a
                        href={s.homepage_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        title={`Open ${s.name} dashboard in a new tab`}
                        className="inline-flex items-center gap-1.5 text-slate-900 hover:text-blue-700 hover:underline transition"
                      >
                        {s.name}
                        <svg className="w-3 h-3 text-slate-400 group-hover:text-blue-500" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                        </svg>
                      </a>
                    ) : (
                      s.name
                    )}
                  </td>
                  <td className="px-3 py-2.5 text-slate-600">{s.type}</td>
                  <td className="px-3 py-2.5 min-w-[260px]">
                    {!s.key_field ? (
                      <span className="text-xs text-slate-400">—</span>
                    ) : isEditing ? (
                      <div className="flex items-center gap-2">
                        <input
                          type="text"
                          autoFocus
                          value={editRow.value}
                          onChange={(e) => setEdit((es) => ({ ...es, [s.id]: { ...editRow, value: e.target.value } }))}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") saveKey(s);
                            if (e.key === "Escape") cancelEdit(s.id);
                          }}
                          disabled={editRow.saving}
                          placeholder={`Paste new ${s.key_field}… (blank = clear)`}
                          className="flex-1 text-xs font-mono bg-white border border-slate-300 rounded px-2 py-1 focus:outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100 disabled:opacity-60"
                        />
                        <button
                          onClick={() => saveKey(s)}
                          disabled={editRow.saving}
                          className="text-xs font-semibold px-2 py-1 rounded bg-blue-600 text-white hover:bg-blue-700 active:scale-95 disabled:opacity-60"
                        >
                          {editRow.saving ? "Saving…" : "Save"}
                        </button>
                        <button
                          onClick={() => cancelEdit(s.id)}
                          disabled={editRow.saving}
                          className="text-xs font-medium px-2 py-1 rounded text-slate-500 hover:text-slate-900"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : s.key_preview ? (
                      <div className="flex items-center gap-2">
                        <code className="text-xs font-mono text-slate-700 bg-slate-100 px-2 py-0.5 rounded">
                          {s.key_preview}
                        </code>
                        <span className={
                          "text-[10px] font-semibold px-1.5 py-0.5 rounded-full " +
                          (s.key_source === "config"
                            ? "bg-emerald-50 text-emerald-700"
                            : "bg-amber-50 text-amber-700")
                        }>
                          {s.key_source === "config" ? "saved in UI" : "from .env"}
                        </span>
                        <button
                          onClick={() => startEdit(s.id)}
                          className="text-xs font-medium text-blue-600 hover:text-blue-800"
                        >
                          Edit
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-medium text-rose-600">Not set</span>
                        <button
                          onClick={() => startEdit(s.id)}
                          className="text-xs font-semibold text-blue-600 hover:text-blue-800"
                        >
                          + Add key
                        </button>
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-2.5 text-right tabular-nums text-slate-700">{s.items_fetched_24h}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums text-slate-700">{s.items_extracted_24h}</td>
                  <td className="px-3 py-2.5 text-slate-600 whitespace-nowrap">{formatIST(s.last_run_at)}</td>
                  <td className="px-3 py-2.5 text-right space-x-2 whitespace-nowrap">
                    <button
                      onClick={async () => { await api.runSource(s.id); load(); }}
                      className="inline-flex items-center gap-1 text-xs font-medium px-3 py-1 rounded-full bg-blue-100 text-blue-700 hover:bg-blue-200 transition-all active:scale-95 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1"
                    >
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                      </svg>
                      Run now
                    </button>
                    <button
                      onClick={async () => { await api.toggleSource(s.id, !s.is_active); load(); }}
                      className={`inline-flex items-center gap-1 text-xs font-medium px-3 py-1 rounded-full transition-all active:scale-95 focus:outline-none focus:ring-2 focus:ring-offset-1 ${
                        s.is_active
                          ? "bg-amber-100 text-amber-700 hover:bg-amber-200 focus:ring-amber-500"
                          : "bg-emerald-100 text-emerald-700 hover:bg-emerald-200 focus:ring-emerald-500"
                      }`}
                    >
                      {s.is_active ? "Pause" : "Activate"}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </AppShell>
  );
}

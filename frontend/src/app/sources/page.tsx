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

  async function load() {
    const r = await api.listSources() as { items: SourceItem[] };
    setItems(r.items);
  }
  useEffect(() => { load(); }, []);

  return (
    <AppShell>
      <h1 className="text-xl font-semibold tracking-tight mb-6">Sources</h1>
      <table className="w-full bg-white rounded-lg border overflow-hidden text-sm">
        <thead className="bg-slate-100 text-slate-600">
          <tr>
            <th className="text-left p-3"></th>
            <th className="text-left p-3">Name</th>
            <th className="text-left p-3">Type</th>
            <th className="text-right p-3">Fetched (last run)</th>
            <th className="text-right p-3">Extracted (last run)</th>
            <th className="text-left p-3">Last run (IST)</th>
            <th className="p-3"></th>
          </tr>
        </thead>
        <tbody>
          {items.map(s => {
            const st = statusOf(s);
            return (
              <tr key={s.id} className="border-t">
                <td className="p-3"><span className={`inline-block w-2.5 h-2.5 rounded-full ${st.color}`} /></td>
                <td className="p-3 font-medium">{s.name}</td>
                <td className="p-3 text-slate-600">{s.type}</td>
                <td className="p-3 text-right">{s.items_fetched_24h}</td>
                <td className="p-3 text-right">{s.items_extracted_24h}</td>
                <td className="p-3 text-slate-600">{formatIST(s.last_run_at)}</td>
                <td className="p-3 text-right space-x-2">
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
    </AppShell>
  );
}

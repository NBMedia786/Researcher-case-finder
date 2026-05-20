"use client";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { CaseRow } from "@/components/case-row";
import { api } from "@/lib/api";
import type { CaseListItem } from "@/lib/types";

const STATUS_OPTIONS = ["new", "reviewing", "approved", "rejected",
                        "foia_filed", "records_received", "archived"];

export default function InboxPage() {
  const [cases, setCases] = useState<CaseListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("new");
  const [state, setState] = useState("");
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const params: Record<string, string | number> = { page, page_size: 25 };
    if (status) params.status = status;
    if (state) params.state = state;
    if (q) params.q = q;
    api.listCases(params)
      .then((r: unknown) => {
        const data = r as { items: CaseListItem[]; total: number };
        setCases(data.items);
        setTotal(data.total);
      })
      .finally(() => setLoading(false));
  }, [page, status, state, q]);

  return (
    <AppShell>
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-semibold tracking-tight mr-auto">Inbox</h1>
        <select value={status} onChange={(e) => { setPage(1); setStatus(e.target.value); }}
                className="border rounded-md px-2 py-1 text-sm bg-white">
          <option value="">All statuses</option>
          {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
        </select>
        <input value={state} onChange={(e) => { setPage(1); setState(e.target.value.toUpperCase()); }}
               placeholder="State (e.g. TX)" maxLength={2}
               className="border rounded-md px-2 py-1 text-sm bg-white w-24" />
        <input value={q} onChange={(e) => { setPage(1); setQ(e.target.value); }}
               placeholder="Search&hellip;" className="border rounded-md px-2 py-1 text-sm bg-white" />
      </div>

      {loading ? (
        <p className="text-slate-500">Loading&hellip;</p>
      ) : cases.length === 0 ? (
        <p className="text-slate-500">No cases match.</p>
      ) : (
        <div className="space-y-3">
          {cases.map(c => <CaseRow key={c.id} c={c} />)}
        </div>
      )}

      <div className="mt-6 flex items-center justify-between text-sm text-slate-600">
        <span>{total} total &middot; page {page} of {Math.max(1, Math.ceil(total / 25))}</span>
        <div className="space-x-2">
          <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1}
                  className="px-3 py-1 border rounded-md disabled:opacity-50">Prev</button>
          <button onClick={() => setPage(page + 1)} disabled={page * 25 >= total}
                  className="px-3 py-1 border rounded-md disabled:opacity-50">Next</button>
        </div>
      </div>
    </AppShell>
  );
}

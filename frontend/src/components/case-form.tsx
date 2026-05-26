"use client";
import { useState } from "react";
import type { CaseDetail } from "@/lib/types";

const FIELDS: { key: keyof CaseDetail; label: string }[] = [
  { key: "defendant_name", label: "Defendant" },
  { key: "defendant_age", label: "Age" },
  { key: "defendant_hometown", label: "Hometown" },
  { key: "court_name", label: "Court" },
  { key: "county", label: "County" },
  { key: "state", label: "State" },
  { key: "docket_number", label: "Docket #" },
  { key: "judge_name", label: "Judge" },
  { key: "prosecuting_office", label: "Prosecuting office" },
  { key: "investigating_agency", label: "Investigating agency" },
];

export function CaseForm({ c, onSave }: { c: CaseDetail; onSave: (patch: Record<string, unknown>) => void }) {
  const [form, setForm] = useState<CaseDetail>({ ...c });
  return (
    <div className="grid grid-cols-2 gap-3">
      {FIELDS.map(f => (
        <label key={String(f.key)} className="text-sm">
          <span className="block text-slate-500 mb-1">{f.label}</span>
          <input
            value={form[f.key] != null ? String(form[f.key]) : ""}
            onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
            className="w-full border rounded-md px-2 py-1 bg-white"
          />
        </label>
      ))}
      <label className="col-span-2 text-sm">
        <span className="block text-slate-500 mb-1">Notes</span>
        <textarea rows={3}
          value={form.notes ?? ""}
          onChange={(e) => setForm({ ...form, notes: e.target.value })}
          className="w-full border rounded-md px-2 py-1 bg-white"
        />
      </label>
      <div className="col-span-2 flex justify-end">
        <button
          onClick={() => {
            const patch: Record<string, unknown> = {};
            FIELDS.forEach(f => {
              if (form[f.key] !== c[f.key]) patch[f.key as string] = form[f.key];
            });
            if (form.notes !== c.notes) patch.notes = form.notes;
            if (Object.keys(patch).length) onSave(patch);
          }}
          className="inline-flex items-center gap-1.5 text-xs font-semibold px-4 py-2 rounded-full bg-blue-600 text-white hover:bg-blue-700 transition-all shadow-sm hover:shadow active:scale-95 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2">
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
          Save changes
        </button>
      </div>
    </div>
  );
}

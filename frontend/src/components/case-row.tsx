"use client";
import Link from "next/link";
import type { CaseListItem } from "@/lib/types";

function Stars({ score }: { score: number }) {
  return (
    <span className="text-amber-500">
      {"★".repeat(score)}
      <span className="text-slate-300">{"★".repeat(5 - score)}</span>
    </span>
  );
}

const STATUS_PILL: Record<string, string> = {
  new: "bg-blue-100 text-blue-700",
  reviewing: "bg-amber-100 text-amber-700",
  approved: "bg-emerald-100 text-emerald-700",
  rejected: "bg-slate-200 text-slate-600",
  foia_filed: "bg-violet-100 text-violet-700",
  records_received: "bg-green-100 text-green-700",
  archived: "bg-slate-100 text-slate-500",
};

export function CaseRow({ c }: { c: CaseListItem }) {
  return (
    <Link href={`/case/${c.id}`} className="block bg-white rounded-lg border p-4 hover:border-slate-400 transition">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3">
            <Stars score={c.content_score} />
            <span className="font-medium truncate">
              {c.defendant_name}{c.defendant_age != null ? `, ${c.defendant_age}` : ""}
            </span>
            {c.defendant_hometown && (
              <span className="text-slate-500 text-sm truncate">&middot; {c.defendant_hometown}</span>
            )}
          </div>
          <div className="text-sm text-slate-700 mt-1">{c.sentence_text || "—"}</div>
          <div className="text-sm text-slate-500 mt-0.5">
            {[c.county, c.state].filter(Boolean).join(", ")} &middot; {c.sentencing_date}
          </div>
        </div>
        <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_PILL[c.status] || "bg-slate-100"}`}>
          {c.status.replace("_", " ")}
        </span>
      </div>
    </Link>
  );
}

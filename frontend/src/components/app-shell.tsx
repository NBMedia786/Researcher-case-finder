"use client";
import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import type { User } from "@/lib/types";

const NAV = [
  { href: "/inbox", label: "Inbox" },
  { href: "/sources", label: "Sources", admin: true },
  { href: "/users", label: "Users", admin: true },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.me()
      .then((u) => setUser(u as User))
      .catch(() => router.replace("/login"))
      .finally(() => setLoading(false));
  }, [router]);

  if (loading) {
    return <div className="min-h-screen flex items-center justify-center text-slate-500">Loading&hellip;</div>;
  }
  if (!user) return null;

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b bg-white">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <Link href="/inbox" className="font-semibold tracking-tight">
            NB Research
          </Link>
          <nav className="flex items-center gap-6 text-sm">
            {NAV.filter(n => !n.admin || user.role === "admin").map(n => (
              <Link
                key={n.href} href={n.href}
                className={`hover:text-slate-900 ${pathname?.startsWith(n.href) ? "text-slate-900 font-medium" : "text-slate-500"}`}
              >{n.label}</Link>
            ))}
            <span className="text-slate-400">|</span>
            <span className="text-slate-700">{user.email}</span>
            <button
              onClick={async () => { await api.logout(); router.push("/login"); }}
              className="text-slate-500 hover:text-red-600"
            >Sign out</button>
          </nav>
        </div>
      </header>
      <main className="max-w-6xl mx-auto p-6">{children}</main>
    </div>
  );
}

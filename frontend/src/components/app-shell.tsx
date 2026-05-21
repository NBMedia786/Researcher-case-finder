"use client";
import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import type { User } from "@/lib/types";

const NAV = [
  { href: "/inbox", label: "Inbox", icon: "📥" },
  { href: "/sources", label: "Sources", icon: "📡", admin: true },
  { href: "/users", label: "Users", icon: "👥", admin: true },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    api.me()
      .then((u) => setUser(u as User))
      .catch(() => router.replace("/login"))
      .finally(() => setLoading(false));
  }, [router]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="text-slate-400 text-sm">Loading…</div>
      </div>
    );
  }
  if (!user) return null;

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b bg-white sticky top-0 z-10 shadow-sm">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link href="/inbox" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-slate-900 to-slate-700 flex items-center justify-center text-white font-bold text-sm">
              NB
            </div>
            <span className="font-semibold tracking-tight text-slate-900">Research</span>
          </Link>

          <nav className="hidden md:flex items-center gap-1">
            {NAV.filter(n => !n.admin || user.role === "admin").map(n => {
              const isActive = pathname?.startsWith(n.href);
              return (
                <Link
                  key={n.href} href={n.href}
                  className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${
                    isActive
                      ? "bg-slate-900 text-white"
                      : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
                  }`}
                >
                  <span className="mr-1.5">{n.icon}</span>{n.label}
                </Link>
              );
            })}
          </nav>

          <div className="relative">
            <button
              onClick={() => setMenuOpen(!menuOpen)}
              className="flex items-center gap-2 hover:bg-slate-100 rounded-md px-2 py-1.5 transition"
            >
              <div className="w-7 h-7 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-white text-xs font-medium">
                {user.email.charAt(0).toUpperCase()}
              </div>
              <span className="hidden sm:inline text-sm text-slate-700">{user.email}</span>
              <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            {menuOpen && (
              <div className="absolute right-0 mt-2 w-56 bg-white rounded-lg border shadow-lg py-1 z-20">
                <div className="px-4 py-2 border-b">
                  <div className="text-sm font-medium text-slate-900">{user.full_name || user.email}</div>
                  <div className="text-xs text-slate-500 capitalize">{user.role}</div>
                </div>
                <button
                  onClick={async () => {
                    await api.logout();
                    router.push("/login");
                  }}
                  className="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50"
                >
                  Sign out
                </button>
              </div>
            )}
          </div>
        </div>
      </header>
      <main className="max-w-7xl mx-auto p-6">{children}</main>
    </div>
  );
}

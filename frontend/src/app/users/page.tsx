"use client";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { api } from "@/lib/api";
import type { User } from "@/lib/types";

export default function UsersPage() {
  const [items, setItems] = useState<User[]>([]);

  async function load() {
    const r = await api.listUsers() as { items: User[] };
    setItems(r.items);
  }
  useEffect(() => { load(); }, []);

  return (
    <AppShell>
      <h1 className="text-xl font-semibold tracking-tight mb-6">Users</h1>
      <table className="w-full bg-white rounded-lg border overflow-hidden text-sm">
        <thead className="bg-slate-100 text-slate-600">
          <tr>
            <th className="text-left p-3">Email</th>
            <th className="text-left p-3">Name</th>
            <th className="text-left p-3">Role</th>
            <th className="text-left p-3">Active</th>
            <th className="text-left p-3">Last login</th>
            <th className="p-3"></th>
          </tr>
        </thead>
        <tbody>
          {items.map(u => (
            <tr key={u.id} className="border-t">
              <td className="p-3">{u.email}</td>
              <td className="p-3 text-slate-700">{u.full_name ?? "—"}</td>
              <td className="p-3">
                <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                  u.role === "admin"
                    ? "bg-violet-100 text-violet-700"
                    : "bg-slate-100 text-slate-700"
                }`}>
                  {u.role}
                </span>
              </td>
              <td className="p-3">
                <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                  u.is_active
                    ? "bg-emerald-100 text-emerald-700"
                    : "bg-slate-200 text-slate-500"
                }`}>
                  {u.is_active ? "active" : "inactive"}
                </span>
              </td>
              <td className="p-3 text-slate-600">{u.last_login_at ?? "—"}</td>
              <td className="p-3 text-right space-x-2">
                <button
                  onClick={async () => {
                    await api.updateUser(u.id, { role: u.role === "admin" ? "researcher" : "admin" });
                    load();
                  }}
                  className="inline-flex items-center text-xs font-medium px-3 py-1 rounded-full bg-violet-100 text-violet-700 hover:bg-violet-200 transition-all active:scale-95 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:ring-offset-1"
                >
                  {u.role === "admin" ? "Demote" : "Promote"}
                </button>
                <button
                  onClick={async () => { await api.updateUser(u.id, { is_active: !u.is_active }); load(); }}
                  className={`inline-flex items-center text-xs font-medium px-3 py-1 rounded-full transition-all active:scale-95 focus:outline-none focus:ring-2 focus:ring-offset-1 ${
                    u.is_active
                      ? "bg-amber-100 text-amber-700 hover:bg-amber-200 focus:ring-amber-500"
                      : "bg-emerald-100 text-emerald-700 hover:bg-emerald-200 focus:ring-emerald-500"
                  }`}
                >
                  {u.is_active ? "Deactivate" : "Activate"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </AppShell>
  );
}

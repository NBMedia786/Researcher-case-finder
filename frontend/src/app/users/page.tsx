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
              <td className="p-3">{u.role}</td>
              <td className="p-3">{u.is_active ? "yes" : "no"}</td>
              <td className="p-3 text-slate-600">{u.last_login_at ?? "—"}</td>
              <td className="p-3 text-right space-x-2">
                <button
                  onClick={async () => {
                    await api.updateUser(u.id, { role: u.role === "admin" ? "researcher" : "admin" });
                    load();
                  }}
                  className="text-xs border rounded-md px-2 py-1">
                  {u.role === "admin" ? "Demote" : "Promote"}
                </button>
                <button
                  onClick={async () => { await api.updateUser(u.id, { is_active: !u.is_active }); load(); }}
                  className="text-xs border rounded-md px-2 py-1">
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

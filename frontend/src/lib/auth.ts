import { api } from "./api";
import type { User } from "./types";

export async function getCurrentUser(): Promise<User | null> {
  try {
    return await api.me() as User;
  } catch {
    return null;
  }
}

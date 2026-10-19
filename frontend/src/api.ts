const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
export type Website = { id: number; url: string; title: string; description: string; category: string;
  country: string | null; language: string | null; date_discovered: string; last_verified: string;
  times_visited: number; times_liked: number; times_disliked: number; hidden_gem_score: number; status: string };
export const token = { get: () => localStorage.getItem("we_token"), set: (t: string | null) => t ? localStorage.setItem("we_token", t) : localStorage.removeItem("we_token") };
export async function api<T = any>(path: string, opts: RequestInit = {}): Promise<T> {
  const t = token.get();
  const res = await fetch(BASE + path, { ...opts, headers: { "Content-Type": "application/json", ...(t ? { Authorization: `Bearer ${t}` } : {}), ...(opts.headers || {}) } });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText);
  return res.json();
}
export const post = <T = any>(p: string, body?: unknown) => api<T>(p, { method: "POST", body: body ? JSON.stringify(body) : undefined });

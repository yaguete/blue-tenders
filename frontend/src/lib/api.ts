export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export type Card = {
  id: string;
  title: string;
  title_en: string | null;
  summary_en: string | null;
  kind: string | null;
  status: string | null;
  programme_id: string | null;
  country: string | null;
  deadline_at: string | null;
  budget_total_eur: number | null;
  amount_max_eur: number | null;
  cofunding_min: number | null;
  cofunding_max: number | null;
  subsectors: string[];
  url: string;
  language: string | null;
  why?: string | null;
  fit?: { level: string; line: string };
};

export type SearchResponse = {
  total: number;
  counts?: { all: number; kind: Record<string, number>; deadline?: Record<string, number> };
  unknown: Record<string, number>;
  suggestion: string | null;
  hidden_ineligible: number;
  facets?: {
    country?: { value: string; count: number }[];
    country_missing?: number;
  };
  items: Card[];
};

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (typeof window !== "undefined") {
    const demo = window.localStorage.getItem("demo-user");
    if (demo) headers.set("X-Demo-User", demo);
  }
  const response = await fetch(`${API_URL}${path}`, { ...init, headers, cache: "no-store" });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed (${response.status})`);
  }
  const type = response.headers.get("content-type") || "";
  if (type.includes("application/json")) return response.json() as Promise<T>;
  return response.text() as Promise<T>;
}

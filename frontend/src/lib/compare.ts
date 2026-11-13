"use client";

import { useEffect, useState } from "react";

const KEY = "compare-ids";
const EVENT = "compare-ids";
export const COMPARE_LIMIT = 4;

function read(): string[] {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(KEY) || "[]");
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((item) => typeof item === "string").slice(0, COMPARE_LIMIT);
  } catch {
    return [];
  }
}

function write(ids: string[]) {
  const next = ids.slice(0, COMPARE_LIMIT);
  window.localStorage.setItem(KEY, JSON.stringify(next));
  window.dispatchEvent(new Event(EVENT));
}

export function comparePath(ids: string[]): string {
  return `/compare?ids=${ids.map(encodeURIComponent).join(",")}`;
}

export function toggleCompare(id: string): string[] {
  const current = read();
  if (current.includes(id)) {
    const next = current.filter((item) => item !== id);
    write(next);
    return next;
  }
  if (current.length >= COMPARE_LIMIT) return current;
  const next = [...current, id];
  write(next);
  return next;
}

export function addCompare(id: string): string[] {
  const current = read();
  if (current.includes(id)) return current;
  if (current.length >= COMPARE_LIMIT) return current;
  const next = [...current, id];
  write(next);
  return next;
}

export function replaceCompare(ids: string[]) {
  write(ids);
}

export function clearCompare() {
  write([]);
}

export function useCompareIds(): string[] {
  const [ids, setIds] = useState<string[]>([]);
  useEffect(() => {
    const sync = () => setIds(read());
    sync();
    window.addEventListener(EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);
  return ids;
}

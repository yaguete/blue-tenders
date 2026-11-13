"use client";

import { useEffect, useState } from "react";
import { api, type Stats } from "@/lib/api";
import type { LandingSearch } from "@/components/landing/format";

export type LoadState<T> =
  | { status: "loading" }
  | { status: "ready"; data: T }
  | { status: "error" };

export type LandingSubsector = {
  id: string;
  name: string;
  keywords: string[];
};

export type LandingVertical = {
  id: string;
  name: string;
  subsectors: LandingSubsector[];
};

const loading = { status: "loading" } as const;

const OPEN = "deadline=open&deadline=closing_soon";

export function useLandingData() {
  const [stats, setStats] = useState<LoadState<Stats>>(loading);
  const [calls, setCalls] = useState<LoadState<LandingSearch>>(loading);
  const [vertical, setVertical] = useState<LoadState<LandingVertical>>(loading);
  const [sectorCounts, setSectorCounts] = useState<Record<string, LoadState<number>>>({});

  useEffect(() => {
    let cancel = false;

    function load<T>(path: string, set: (next: LoadState<T>) => void) {
      api<T>(path)
        .then((data) => {
          if (!cancel) set({ status: "ready", data });
        })
        .catch(() => {
          if (!cancel) set({ status: "error" });
        });
    }

    load<Stats>("/opportunities/stats", setStats);
    load<LandingSearch>(`/opportunities?${OPEN}&limit=100`, setCalls);
    load<LandingVertical>("/vertical", setVertical);

    return () => {
      cancel = true;
    };
  }, []);

  useEffect(() => {
    if (vertical.status !== "ready") return;
    let cancel = false;
    const ids = vertical.data.subsectors.map((subsector) => subsector.id);
    setSectorCounts(Object.fromEntries(ids.map((id) => [id, loading])));
    for (const id of ids) {
      const path =
        `/opportunities?subsector=${encodeURIComponent(id)}&${OPEN}&exclude_unknown=true&limit=0`;
      api<LandingSearch>(path)
        .then((data) => {
          if (!cancel) setSectorCounts((current) => ({ ...current, [id]: { status: "ready", data: data.total } }));
        })
        .catch(() => {
          if (!cancel) setSectorCounts((current) => ({ ...current, [id]: { status: "error" } }));
        });
    }
    return () => {
      cancel = true;
    };
  }, [vertical]);

  return { stats, calls, vertical, sectorCounts };
}

"use client";

import { useEffect, useState } from "react";
import { t } from "@/lib/i18n";

const CYCLE = ["assistantPhaseReading", "assistantPhaseSearching", "assistantPhaseThinking"] as const;

const STATUS: Record<string, string> = {
  searching: "assistantStatusSearching",
  reading: "assistantStatusReading",
  glossary: "assistantStatusGlossary",
  funders: "assistantStatusFunders",
  documents: "assistantStatusDocuments",
  web: "assistantStatusWeb",
};

export function Loading({ status }: { status: string | null }) {
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (status) return;
    const timer = window.setInterval(() => setTick((current) => current + 1), 2000);
    return () => window.clearInterval(timer);
  }, [status]);

  const key = (status && STATUS[status]) || CYCLE[tick % CYCLE.length];
  const label = t(key).replace(/…|\.\.\.$/, "");

  return (
    <p className="assistant-shimmer text-xs" aria-hidden>
      {label}{" "}
      <span className="assistant-dots">
        <span>.</span>
        <span>.</span>
        <span>.</span>
      </span>
    </p>
  );
}

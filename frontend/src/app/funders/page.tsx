"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { t } from "@/lib/i18n";

type Funder = {
  id: string;
  name: string;
  kind: string;
  url: string;
  summary: string;
  instruments: string[];
  geographies: string[];
  last_verified: string | null;
};

export default function FundersPage() {
  const [rows, setRows] = useState<Funder[] | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    api<Funder[]>("/funders").then(setRows).catch(() => setError(true));
  }, []);
  if (error) return <p className="text-sm">{t("error")}</p>;
  if (!rows) return <p className="text-sm text-muted-foreground">{t("loading")}</p>;
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold tracking-tight">Funders without a deadline</h1>
      <p className="max-w-xl text-sm text-muted-foreground">
        Loans, equity and philanthropy that are not published as a call. Ticket sizes are omitted when the
        source page does not state them.
      </p>
      <ul className="divide-y divide-border">
        {rows.map((row) => (
          <li key={row.id} className="grid gap-2 py-4 md:grid-cols-[12rem_1fr]">
            <p className="font-mono text-xs text-muted-foreground">
              {row.kind}
              <br />
              {row.instruments.join(", ")}
              <br />
              {row.geographies.join(", ") || "—"}
            </p>
            <div>
              <a href={row.url} className="font-medium underline">
                {row.name}
              </a>
              <p className="mt-1 text-sm text-muted-foreground">{row.summary}</p>
              {row.last_verified && (
                <p className="mt-1 font-mono text-xs text-muted-foreground">Checked {row.last_verified}</p>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

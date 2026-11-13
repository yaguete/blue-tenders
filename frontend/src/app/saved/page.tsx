"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { t } from "@/lib/i18n";

export default function SavedPage() {
  const [rows, setRows] = useState<{ opportunity_id: string }[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api<{ opportunity_id: string }[]>("/saved")
      .then(setRows)
      .catch((err: Error) => setError(err.message));
  }, []);
  if (error) return <p className="text-sm">{t("signIn")}</p>;
  if (!rows) return <p className="text-sm text-muted-foreground">{t("loading")}</p>;
  if (rows.length === 0) return <p className="text-sm">{t("empty")}</p>;
  return (
    <ul className="space-y-2 text-sm">
      {rows.map((row) => (
        <li key={row.opportunity_id}>
          <Link className="underline" href={`/opportunities/${row.opportunity_id}`}>
            {row.opportunity_id}
          </Link>
        </li>
      ))}
    </ul>
  );
}

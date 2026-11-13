"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { LoadingState } from "@/components/loading-state";
import { api } from "@/lib/api";
import { replaceCompare } from "@/lib/compare";
import { money, when } from "@/lib/format";
import { t } from "@/lib/i18n";

type Row = {
  id: string;
  title: string;
  title_en: string | null;
  deadline_at: string | null;
  budget_total_eur: number | null;
  amount_max_eur: number | null;
  kind: string | null;
  programme_id: string | null;
  country: string | null;
  cofunding_min: number | null;
  cofunding_max: number | null;
  consortium_required: boolean | null;
};

function cofunding(row: Row): string {
  if (row.cofunding_min == null && row.cofunding_max == null) return "—";
  return `${row.cofunding_min ?? "?"}–${row.cofunding_max ?? "?"}%`;
}

function consortium(row: Row): string {
  if (row.consortium_required == null) return "Not specified";
  return row.consortium_required ? "Required" : "Not required";
}

function CompareInner() {
  const params = useSearchParams();
  const router = useRouter();
  const ids = (params.get("ids") || "")
    .split(",")
    .map((value) => {
      try {
        return decodeURIComponent(value);
      } catch {
        return value;
      }
    })
    .filter(Boolean)
    .slice(0, 4);
  const idList = ids.join(",");
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState(false);

  useEffect(() => {
    const chosen = idList.split(",").filter(Boolean);
    if (chosen.length) replaceCompare(chosen);
    if (chosen.length < 2) router.replace("/search");
  }, [idList, router]);

  useEffect(() => {
    const chosen = idList.split(",").filter(Boolean);
    if (chosen.length < 2) return;
    Promise.all(chosen.map((id) => api<Row>(`/opportunities/${id}`)))
      .then((found) => {
        setRows(found);
        setError(false);
      })
      .catch(() => setError(true));
  }, [idList]);

  if (ids.length < 2) {
    return (
      <p className="text-sm">
        {t("compareEmpty")}{" "}
        <Link className="underline" href="/search">
          Search
        </Link>
      </p>
    );
  }
  if (error) return <p className="text-sm">{t("error")}</p>;
  if (rows.length < 2) return <LoadingState label={t("loading")} />;

  const fields: [string, (row: Row) => string][] = [
    ["Deadline", (row) => when(row.deadline_at)],
    ["Budget", (row) => money(row.budget_total_eur || row.amount_max_eur)],
    ["Kind", (row) => row.kind || "—"],
    ["Programme", (row) => row.programme_id || "—"],
    ["Country", (row) => row.country || "—"],
    ["Co-funding", cofunding],
    ["Consortium", consortium],
  ];

  function drop(id: string) {
    const next = ids.filter((item) => item !== id);
    replaceCompare(next);
    router.push("/search");
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr>
            <th className="p-2" />
            {rows.map((row) => (
              <th key={row.id} className="p-2 align-top font-medium">
                <Link href={`/opportunities/${row.id}`} className="hover:underline">
                  {row.title_en || row.title}
                </Link>
                <button type="button" className="mt-2 block cursor-pointer text-xs font-normal underline" onClick={() => drop(row.id)}>
                  {t("remove")}
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {fields.map(([label, read]) => (
            <tr key={label} className="border-t border-border">
              <th className="p-2 font-mono text-xs font-normal text-muted-foreground">{label}</th>
              {rows.map((row) => (
                <td key={row.id} className="tabular p-2">
                  {read(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ComparePage() {
  return (
    <Suspense fallback={<LoadingState label={t("loading")} />}>
      <CompareInner />
    </Suspense>
  );
}

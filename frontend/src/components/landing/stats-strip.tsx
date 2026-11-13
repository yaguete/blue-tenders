"use client";

import Link from "next/link";
import { landingCount } from "@/components/landing/format";
import type { LoadState } from "@/components/landing/use-landing-data";
import type { Stats } from "@/lib/api";
import { clearCompare } from "@/lib/compare";
import { checkedAt } from "@/lib/format";
import { t } from "@/lib/i18n";
import { cn } from "@/lib/utils";

type Cell = {
  label: string;
  value: string;
  note?: string;
  href?: string;
};

export function StatsStrip({ stats }: { stats: LoadState<Stats> }) {
  if (stats.status === "error") return null;
  const data = stats.status === "ready" ? stats.data : null;
  const cells: Cell[] = [
    {
      label: t("statsOpen"),
      value: data ? landingCount(data.open + data.closing_soon) : "—",
      href: "/search",
    },
    {
      label: t("landingStatClosing"),
      value: data ? landingCount(data.closing_soon) : "—",
      href: "/search?deadline=closing_soon",
    },
    {
      label: t("statsPast"),
      value: data ? landingCount(data.closed) : "—",
      note: data ? t("statsPastNote") : undefined,
      href: "/search?deadline=closed",
    },
    {
      label: t("statsSources"),
      value: data ? landingCount(data.sources) : "—",
      note: data?.checked_at ? checkedAt(data.checked_at) : undefined,
    },
  ];

  return (
    <section aria-label={t("landingStatsLabel")}>
      <div className="grid grid-cols-2 border-y border-border md:grid-cols-4">
        {cells.map((cell, index) => {
          const className = cn(
            "min-w-0 py-8 pr-6",
            index % 2 === 1 && "border-l border-border pl-6",
            index >= 2 && "border-t border-border",
            index > 0 && "md:border-t-0 md:border-l md:border-border md:pl-6",
            cell.href &&
              "block focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-ring",
          );
          const body = (
            <>
              <p className="text-sm text-muted-foreground">{cell.label}</p>
              <p className="mt-3 flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <span className="text-[40px] leading-none font-semibold tabular-nums">{cell.value}</span>
                {cell.note && <span className="text-sm text-muted-foreground">{cell.note}</span>}
              </p>
            </>
          );
          if (!cell.href) {
            return (
              <div key={cell.label} className={className}>
                {body}
              </div>
            );
          }
          return (
            <Link key={cell.label} href={cell.href} onClick={() => clearCompare()} className={className}>
              {body}
            </Link>
          );
        })}
      </div>
    </section>
  );
}

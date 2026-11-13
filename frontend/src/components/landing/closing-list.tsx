"use client";

import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { SectionKicker } from "@/components/landing/section-kicker";
import { landingCount, landingDeadline, landingMeta, landingMoney, landingShowcase, landingTitle } from "@/components/landing/format";
import type { LandingSearch } from "@/components/landing/format";
import type { LoadState } from "@/components/landing/use-landing-data";
import { LoadingState } from "@/components/loading-state";
import type { Stats } from "@/lib/api";
import { clearCompare } from "@/lib/compare";
import { when } from "@/lib/format";
import { t } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export function ClosingList({
  n,
  calls,
  stats,
}: {
  n: number;
  calls: LoadState<LandingSearch>;
  stats: LoadState<Stats>;
}) {
  const items = calls.status === "ready" ? landingShowcase(calls.data.items) : [];
  const openTotal =
    stats.status === "ready"
      ? stats.data.open + stats.data.closing_soon
      : calls.status === "ready"
        ? calls.data.total
        : null;

  return (
    <section>
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="max-w-xl">
          <SectionKicker n={n} label={t("landingClosingKicker")} />
          <h2 className="mt-3 text-3xl font-semibold tracking-[-0.03em] text-balance">{t("landingClosingTitle")}</h2>
        </div>
        <p className="max-w-sm text-sm text-foreground/80 sm:text-right">{t("landingClosingNote")}</p>
      </header>
      {calls.status === "loading" && <LoadingState label={t("loading")} className="mt-8" />}
      {calls.status === "error" && <p className="mt-8 text-sm text-status-urgent">{t("landingClosingError")}</p>}
      {calls.status === "ready" && calls.data.total === 0 && (
        <p className="mt-8 text-sm text-muted-foreground">{t("landingClosingEmpty")}</p>
      )}
      {items.length > 0 && (
        <ul className="mt-8 border-t border-border">
          {items.map((item, index) => {
            const deadline = landingDeadline(item.deadline_at);
            const title = landingTitle(item.title, item.title_en);
            const meta = landingMeta(item.kind, item.programme_id, item.country);
            const money = landingMoney(item.budget_total_eur, item.amount_max_eur);
            return (
              <li key={item.id} className="border-b border-border">
                <Link
                  href={`/opportunities/${item.id}`}
                  className="group grid grid-cols-[auto_minmax(0,1fr)_auto] items-start gap-x-3 py-[22px] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring sm:grid-cols-[2.5rem_minmax(0,1fr)_8.5rem_10.5rem_auto] sm:items-center sm:gap-x-6"
                >
                  <span className="pt-1 font-mono text-xs text-muted-foreground tabular-nums sm:pt-0">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <span className="min-w-0">
                    <span className="line-clamp-2 block text-lg leading-6 font-semibold group-hover:underline">
                      {title}
                    </span>
                    {meta && <span className="mt-1 block font-mono text-xs text-muted-foreground">{meta}</span>}
                    <span className="mt-3 flex items-start justify-between gap-4 sm:hidden">
                      <Money value={money} />
                      <Deadline label={deadline.label} urgent={deadline.urgent} date={when(item.deadline_at)} />
                    </span>
                  </span>
                  <ArrowUpRight className="mt-1 size-4 shrink-0 sm:hidden" aria-hidden />
                  <Money value={money} className="hidden sm:block sm:text-right" />
                  <Deadline
                    label={deadline.label}
                    urgent={deadline.urgent}
                    date={when(item.deadline_at)}
                    className="hidden sm:block"
                  />
                  <ArrowUpRight className="hidden size-4 shrink-0 sm:block" aria-hidden />
                </Link>
              </li>
            );
          })}
        </ul>
      )}
      {openTotal != null && openTotal > 0 && (
        <p className="mt-6">
          <Link
            href="/search"
            onClick={() => clearCompare()}
            className="text-sm text-brand-blue focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring"
          >
            {(openTotal === 1 ? t("landingSeeAllOne") : t("landingSeeAll")).replace("{count}", landingCount(openTotal))}
          </Link>
        </p>
      )}
    </section>
  );
}

function Money({ value, className }: { value: string; className?: string }) {
  return <span className={cn("font-mono text-sm tabular-nums", className)}>{value}</span>;
}

function Deadline({
  label,
  urgent,
  date,
  className,
}: {
  label: string | null;
  urgent: boolean;
  date: string;
  className?: string;
}) {
  return (
    <span className={cn("block text-right", className)}>
      {label && (
        <span className={cn("block font-mono text-sm tabular-nums", urgent && "text-deadline-urgent")}>{label}</span>
      )}
      <span className="mt-0.5 block font-mono text-xs text-muted-foreground">{date}</span>
    </span>
  );
}

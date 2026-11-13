"use client";

import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { SectionKicker } from "@/components/landing/section-kicker";
import { landingCount, landingMeta, landingTitle } from "@/components/landing/format";
import type { LandingSearch } from "@/components/landing/format";
import type { LoadState } from "@/components/landing/use-landing-data";
import { LoadingState } from "@/components/loading-state";
import { clearCompare } from "@/lib/compare";
import { calendarDay } from "@/lib/format";
import { t } from "@/lib/i18n";

const SHOWN = 6;

export function ComingList({ n, calls }: { n: number; calls: LoadState<LandingSearch> }) {
  const items = calls.status === "ready" ? calls.data.items.slice(0, SHOWN) : [];
  const total = calls.status === "ready" ? calls.data.total : null;

  return (
    <section>
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="max-w-xl">
          <SectionKicker n={n} label={t("landingComingKicker")} />
          <h2 className="mt-3 text-3xl font-semibold tracking-[-0.03em] text-balance">{t("landingComingTitle")}</h2>
        </div>
        <p className="max-w-sm text-sm text-foreground/80 sm:text-right">{t("landingComingNote")}</p>
      </header>
      {calls.status === "loading" && <LoadingState label={t("loading")} className="mt-8" />}
      {calls.status === "error" && <p className="mt-8 text-sm text-status-urgent">{t("landingComingError")}</p>}
      {calls.status === "ready" && calls.data.total === 0 && (
        <p className="mt-8 text-sm text-muted-foreground">{t("landingComingEmpty")}</p>
      )}
      {items.length > 0 && (
        <ul className="mt-8 border-t border-border">
          {items.map((item, index) => {
            const title = landingTitle(item.title, item.title_en);
            const meta = landingMeta(item.kind, item.programme_id, item.country);
            const seen = item.published_at
              ? t("landingSeen").replace("{date}", calendarDay(item.published_at))
              : calendarDay(null);
            return (
              <li key={item.id} className="border-b border-border">
                <Link
                  href={`/opportunities/${item.id}`}
                  className="group grid grid-cols-[auto_minmax(0,1fr)_auto] items-start gap-x-3 py-[22px] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring sm:grid-cols-[2.5rem_minmax(0,1fr)_auto_auto] sm:items-center sm:gap-x-6"
                >
                  <span className="pt-1 font-mono text-xs text-muted-foreground tabular-nums sm:pt-0">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <span className="min-w-0">
                    <span className="line-clamp-2 block text-lg leading-6 font-semibold group-hover:underline">
                      {title}
                    </span>
                    {meta && <span className="mt-1 block font-mono text-xs text-muted-foreground">{meta}</span>}
                    <span className="mt-3 block font-mono text-xs text-muted-foreground sm:hidden">{seen}</span>
                  </span>
                  <ArrowUpRight className="mt-1 size-4 shrink-0 sm:hidden" aria-hidden />
                  <span className="hidden font-mono text-sm text-muted-foreground sm:block">{seen}</span>
                  <ArrowUpRight className="hidden size-4 shrink-0 sm:block" aria-hidden />
                </Link>
              </li>
            );
          })}
        </ul>
      )}
      {total != null && total > 0 && (
        <p className="mt-6">
          <Link
            href="/search?deadline=upcoming"
            onClick={() => clearCompare()}
            className="text-sm text-brand-blue focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring"
          >
            {(total === 1 ? t("landingComingSeeAllOne") : t("landingComingSeeAll")).replace(
              "{count}",
              landingCount(total),
            )}
          </Link>
        </p>
      )}
    </section>
  );
}

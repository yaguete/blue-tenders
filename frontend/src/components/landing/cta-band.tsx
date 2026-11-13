"use client";

import Link from "next/link";
import { clearCompare } from "@/lib/compare";
import { t } from "@/lib/i18n";
import { landingCount } from "@/components/landing/format";
import type { LoadState } from "@/components/landing/use-landing-data";
import type { Stats } from "@/lib/api";

export function CtaBand({ stats }: { stats: LoadState<Stats> }) {
  const total = stats.status === "ready" ? stats.data.open + stats.data.closing_soon : null;
  const heading =
    total == null
      ? t("landingCtaFallback")
      : (total === 1 ? t("landingCtaCountOne") : t("landingCtaCount")).replace("{count}", landingCount(total));

  return (
    <section className="bg-brand-pale px-6 py-16 sm:px-12">
      <h2 className="max-w-[18ch] text-3xl font-semibold tracking-[-0.03em] text-balance">{heading}</h2>
      <p className="mt-4 max-w-md text-foreground/80">{t("landingCtaNote")}</p>
      <Link
        href="/search"
        onClick={() => clearCompare()}
        className="mt-8 inline-flex h-[54px] items-center bg-primary px-6 text-sm text-primary-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
      >
        {t("landingSearchButton")}
      </Link>
    </section>
  );
}

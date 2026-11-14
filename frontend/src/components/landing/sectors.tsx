"use client";

import Link from "next/link";
import { Anchor, Cable, Droplets, Ship, Waves, Wind, type LucideIcon } from "lucide-react";
import { SectionKicker } from "@/components/landing/section-kicker";
import { landingCount, sectorQuery } from "@/components/landing/format";
import type { LandingVertical, LoadState } from "@/components/landing/use-landing-data";
import { clearCompare } from "@/lib/compare";
import { t } from "@/lib/i18n";

const ICONS: Record<string, LucideIcon> = {
  "offshore-wind": Wind,
  "ocean-energy": Waves,
  "offshore-hydrogen": Droplets,
  "green-ports": Anchor,
  "fleet-decarbonisation": Ship,
  "subsea-cables": Cable,
};

export function Sectors({
  n,
  vertical,
  counts,
}: {
  n: number;
  vertical: LoadState<LandingVertical>;
  counts: Record<string, LoadState<number>>;
}) {
  if (vertical.status !== "ready") return null;

  return (
    <section>
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="max-w-xl">
          <SectionKicker n={n} label={t("landingSectorsKicker")} />
          <h2 className="mt-3 text-3xl font-semibold tracking-[-0.03em] text-balance">{t("landingSectorsTitle")}</h2>
        </div>
        <p className="max-w-sm text-sm text-foreground/80 sm:text-right">{t("landingSectorsNote")}</p>
      </header>
      <ul className="mt-10 grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(min(100%,320px),1fr))]">
        {vertical.data.subsectors.map((subsector) => {
          const blurbKey = `landingSectors.${subsector.id}`;
          const blurb = t(blurbKey);
          const line = blurb !== blurbKey ? blurb : null;
          const term = sectorQuery(subsector.keywords);
          const href = term ? `/search?q=${encodeURIComponent(term)}` : "/search";
          const Icon = ICONS[subsector.id];
          return (
            <li key={subsector.id} className="border border-border">
              <Link
                href={href}
                onClick={() => clearCompare()}
                className="flex h-full flex-col p-6 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-ring"
              >
                <p className="flex items-center gap-2 font-mono text-xs text-muted-foreground">
                  {Icon && <Icon className="size-4 shrink-0" aria-hidden />}
                  {subsector.id}
                </p>
                <h3 className="mt-3 text-xl font-semibold tracking-tight">{subsector.name}</h3>
                {line && <p className="mt-2 text-sm text-foreground/80">{line}</p>}
                <Count count={counts[subsector.id]} />
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function Count({ count }: { count: LoadState<number> | undefined }) {
  if (!count || count.status !== "ready") return null;
  if (count.data === 0) {
    return <p className="mt-8 text-sm text-muted-foreground">{t("landingSectorNone")}</p>;
  }
  const key = count.data === 1 ? "landingSectorOpenOne" : "landingSectorOpen";
  return (
    <p className="mt-8 text-sm text-brand-blue">{t(key).replace("{count}", landingCount(count.data))} →</p>
  );
}

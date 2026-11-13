"use client";

import { CtaBand } from "@/components/landing/cta-band";
import { ClosingList } from "@/components/landing/closing-list";
import { landingFont } from "@/components/landing/fonts";
import { Hero } from "@/components/landing/hero";
import { HowItWorks } from "@/components/landing/how-it-works";
import { Sectors } from "@/components/landing/sectors";
import { StatsStrip } from "@/components/landing/stats-strip";
import { useLandingData } from "@/components/landing/use-landing-data";
import { cn } from "@/lib/utils";

export default function Home() {
  const { stats, calls, vertical, sectorCounts } = useLandingData();
  const showSectors = vertical.status === "ready";
  const numbered = ["closing", ...(showSectors ? ["sectors"] : []), "how"];
  const sectionNumber = (id: string) => numbered.indexOf(id) + 1;

  return (
    <div
      className={cn(
        landingFont.variable,
        "[font-family:var(--font-landing),sans-serif] [&_button]:[font-family:inherit] [&_input]:[font-family:inherit]",
      )}
    >
      <Hero />
      <div className="flex flex-col gap-28 pb-8">
        <StatsStrip stats={stats} />
        <ClosingList n={sectionNumber("closing")} calls={calls} stats={stats} />
        {showSectors && <Sectors n={sectionNumber("sectors")} vertical={vertical} counts={sectorCounts} />}
        <HowItWorks n={sectionNumber("how")} />
        <CtaBand stats={stats} />
      </div>
    </div>
  );
}

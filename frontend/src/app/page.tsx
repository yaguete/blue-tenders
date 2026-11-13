"use client";

import Link from "next/link";
import { clearCompare } from "@/lib/compare";

export default function Home() {
  return (
    <div className="max-w-xl space-y-6">
      <p className="font-mono text-xs text-muted-foreground">Marine energy · EU and Spain</p>
      <h1 className="text-4xl font-semibold tracking-tight">Find the call. See who has done it before.</h1>
      <p className="text-muted-foreground">
        Grants, public tenders and a short list of funders, classified for offshore wind, ocean energy,
        ports, fleets and subsea cables. Figures on a page point at the official text.
      </p>
      <Link
        href="/search"
        onClick={() => clearCompare()}
        className="inline-flex h-10 items-center bg-primary px-4 text-sm text-primary-foreground"
      >
        Search calls
      </Link>
    </div>
  );
}

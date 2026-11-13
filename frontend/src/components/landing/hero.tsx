"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";
import { clearCompare } from "@/lib/compare";
import { t } from "@/lib/i18n";

export function Hero() {
  const router = useRouter();
  const [query, setQuery] = useState("");

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const q = query.trim();
    clearCompare();
    router.push(q ? `/search?q=${encodeURIComponent(q)}` : "/search");
  }

  return (
    <section className="relative pt-2 pb-28 sm:pt-12">
      <p className="font-mono text-xs tracking-[0.16em] text-muted-foreground uppercase">
        {t("landingEyebrow")}
      </p>
      <h1 className="mt-4 text-[clamp(2.75rem,5.2vw,4.75rem)] font-semibold leading-[1.02] tracking-[-0.04em] text-balance">
        <span className="block">{t("landingTitleLine1")}</span>
        <span className="block text-brand-blue">{t("landingTitleLine2")}</span>
      </h1>
      <p className="mt-6 max-w-[46ch] text-lg text-foreground/80">{t("landingSubcopy")}</p>
      <form role="search" onSubmit={onSubmit} className="mt-8 flex w-full max-w-xl flex-col gap-2 sm:flex-row">
        <label htmlFor="q" className="sr-only">
          {t("landingSearchLabel")}
        </label>
        <input
          id="q"
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t("landingSearchPlaceholder")}
          autoComplete="off"
          className="h-[54px] w-full border border-border bg-background px-4 text-base outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
        />
        <button
          type="submit"
          className="inline-flex h-[54px] shrink-0 cursor-pointer items-center justify-center bg-primary px-6 text-sm text-primary-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          {t("landingSearchButton")}
        </button>
      </form>
      <p className="mt-4 text-sm text-muted-foreground">
        {t("landingAskLead")}{" "}
        <button
          type="button"
          className="cursor-pointer underline decoration-foreground/40 underline-offset-4 hover:text-foreground hover:decoration-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
          onClick={() => window.dispatchEvent(new Event("assistant-open"))}
        >
          {t("landingAskLink")}
        </button>{" "}
        {t("landingAskRest")}
      </p>
    </section>
  );
}

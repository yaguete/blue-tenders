"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { addCompare, COMPARE_LIMIT, comparePath, useCompareIds } from "@/lib/compare";
import { money, when } from "@/lib/format";
import { t } from "@/lib/i18n";

type Block = {
  heading: string;
  text: string;
  origin: "extracted" | "generated";
  citations: { quote?: string | null }[];
};

type Detail = {
  id: string;
  title: string;
  title_en: string | null;
  url: string;
  kind: string;
  programme_id: string | null;
  funder_id: string | null;
  deadline_at: string | null;
  budget_total_eur: number | null;
  cofunding_min: number | null;
  cofunding_max: number | null;
  consortium_required: boolean | null;
  summary_en: string | null;
  description: string | null;
  analysis: { blocks: Block[] } | null;
};

export function CallPreview({ id, onClose }: { id: string; onClose: () => void }) {
  const router = useRouter();
  const compareIds = useCompareIds();
  const closeRef = useRef<HTMLButtonElement>(null);
  const onCloseRef = useRef(onClose);
  const [item, setItem] = useState<Detail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  onCloseRef.current = onClose;

  useEffect(() => {
    let cancel = false;
    api<Detail>(`/opportunities/${id}`)
      .then((found) => {
        if (!cancel) setItem(found);
      })
      .catch((err: Error) => {
        if (!cancel) setError(err.message);
      });
    return () => {
      cancel = true;
    };
  }, [id]);

  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCloseRef.current();
    };
    document.addEventListener("keydown", onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, []);

  function confirm() {
    if (!item) return;
    if (!compareIds.includes(item.id) && compareIds.length >= COMPARE_LIMIT) {
      setNote(t("compareFull"));
      return;
    }
    const next = addCompare(item.id);
    onClose();
    if (next.length >= 2) router.push(comparePath(next));
  }

  const cofunding =
    item && item.cofunding_min == null && item.cofunding_max == null
      ? "—"
      : item
        ? `${item.cofunding_min ?? "?"}–${item.cofunding_max ?? "?"}%`
        : "—";

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-[oklch(0.22_0.02_250/0.45)] px-4 py-8 sm:py-14"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="call-preview-title"
        className="flex max-h-[calc(100vh-4rem)] w-full max-w-2xl flex-col border border-border bg-background shadow-lg sm:max-h-[calc(100vh-7rem)]"
      >
        <div className="flex justify-end px-3 py-2">
          <button
            ref={closeRef}
            type="button"
            aria-label={t("close")}
            onClick={onClose}
            className="cursor-pointer px-2 text-xl leading-none"
          >
            ×
          </button>
        </div>
        <div className="overflow-y-auto px-6 py-5">
          {error && <p className="text-sm text-status-urgent">{t("error")}</p>}
          {!item && !error && <p className="text-sm text-muted-foreground">{t("loading")}</p>}
          {item && (
            <article className="space-y-6">
              <header className="space-y-3">
                <p className="font-mono text-xs text-muted-foreground">
                  {item.kind} · {item.funder_id || "—"} · {item.programme_id || "—"}
                </p>
                <h2 id="call-preview-title" className="text-2xl font-semibold tracking-tight">
                  {item.title_en || item.title}
                </h2>
                <dl className="grid gap-3 text-sm sm:grid-cols-2">
                  <Fact label="Deadline" value={when(item.deadline_at)} />
                  <Fact label="Budget" value={money(item.budget_total_eur)} />
                  <Fact label="Co-funding" value={cofunding} />
                  <Fact
                    label="Consortium"
                    value={
                      item.consortium_required == null
                        ? "Not specified"
                        : item.consortium_required
                          ? "Required"
                          : "Not required"
                    }
                  />
                </dl>
                <div className="flex items-center gap-4">
                  <a className="text-sm underline" href={item.url}>
                    Official call
                  </a>
                  <button
                    type="button"
                    onClick={confirm}
                    className="cursor-pointer bg-primary px-3 py-1.5 text-sm text-primary-foreground"
                  >
                    {t("compare")}
                  </button>
                </div>
                {note && <p className="text-sm text-muted-foreground">{note}</p>}
              </header>
              {item.analysis?.blocks.map((block) => (
                <section key={block.heading} className="space-y-2">
                  <h3 className="text-lg font-semibold">{block.heading}</h3>
                  <p className="text-sm leading-6">{block.text}</p>
                  <p className="font-mono text-xs text-muted-foreground">
                    {block.origin === "extracted" ? t("extracted") : t("generated")}
                    {block.citations[0]?.quote ? ` · “${block.citations[0].quote}”` : ""}
                  </p>
                </section>
              ))}
              {!item.analysis?.blocks.length && (item.summary_en || item.description) && (
                <p className="text-sm leading-6">{item.summary_en || item.description}</p>
              )}
            </article>
          )}
        </div>
      </div>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="font-mono text-xs text-muted-foreground">{label}</dt>
      <dd className="tabular">{value}</dd>
    </div>
  );
}

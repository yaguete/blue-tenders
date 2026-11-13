"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useId, useRef, useState } from "react";
import { CallPreview } from "@/components/call-preview";
import { LoadingState } from "@/components/loading-state";
import { api, type Card, type SearchResponse } from "@/lib/api";
import { comparePath, toggleCompare, useCompareIds } from "@/lib/compare";
import { daysLeft, money, when } from "@/lib/format";
import { t } from "@/lib/i18n";

const KINDS = [
  ["grant", "Grant"],
  ["tender", "Tender"],
  ["loan", "Loan"],
  ["prize", "Prize"],
  ["technical_assistance", "Technical Assistance"],
  ["blended", "Blended"],
] as const;

const KIND_IDS = KINDS.map(([id]) => id);

const DEADLINES = [
  ["open", "deadlineOpen"],
  ["closing_soon", "deadlineClosing"],
  ["closed", "deadlineClosed"],
] as const;

const DEADLINE_IDS = DEADLINES.map(([id]) => id);
const NONE = "none";

function readList(params: URLSearchParams, key: string, all: readonly string[]): string[] {
  const values = params.getAll(key);
  if (values.length === 0) return [...all];
  if (values.length === 1 && values[0] === NONE) return [];
  return values.filter((value) => all.includes(value));
}

function readCountries(params: URLSearchParams): string[] | null {
  const values = params.getAll("country");
  if (values.length === 0) return null;
  if (values.length === 1 && values[0] === NONE) return [];
  return values;
}

function writeList(params: URLSearchParams, key: string, selected: string[], all: readonly string[]) {
  if (selected.length === 0) {
    params.append(key, NONE);
    return;
  }
  if (selected.length >= all.length && all.every((id) => selected.includes(id))) return;
  for (const id of all) {
    if (selected.includes(id)) params.append(key, id);
  }
}

function writeCountries(params: URLSearchParams, countries: string[] | null) {
  if (countries === null) return;
  if (countries.length === 0) {
    params.append("country", NONE);
    return;
  }
  for (const id of [...countries].sort()) params.append("country", id);
}

function searchQuery(q: string, kinds: string[], deadlines: string[], countries: string[] | null): string {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  writeList(params, "kind", kinds, KIND_IDS);
  writeList(params, "deadline", deadlines, DEADLINE_IDS);
  writeCountries(params, countries);
  return params.toString();
}

function sameList(left: string[], right: string[]): boolean {
  if (left.length !== right.length) return false;
  const a = [...left].sort();
  const b = [...right].sort();
  return a.every((value, index) => value === b[index]);
}

function sameCountries(left: string[] | null, right: string[] | null): boolean {
  if (left === null || right === null) return left === right;
  return sameList(left, right);
}

function SearchScreen() {
  const params = useSearchParams();
  const router = useRouter();
  const queryString = params.toString();
  const [q, setQ] = useState(() => params.get("q") ?? "");
  const [selected, setSelected] = useState<string[]>(() => readList(params, "kind", KIND_IDS));
  const [data, setData] = useState<SearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [countries, setCountries] = useState<string[] | null>(() => readCountries(params));
  const [deadlines, setDeadlines] = useState<string[]>(() => readList(params, "deadline", DEADLINE_IDS));
  const [seen, setSeen] = useState(queryString);
  const selectionKey = [...selected].sort().join(",");
  const countryKey = countries === null ? "*" : [...countries].sort().join(",");
  const deadlineKey = [...deadlines].sort().join(",");
  const skipUrl = useRef(queryString);

  if (seen !== queryString && queryString !== skipUrl.current) {
    const incoming = new URLSearchParams(queryString);
    const nextQ = incoming.get("q") ?? "";
    const nextKinds = readList(incoming, "kind", KIND_IDS);
    const nextDeadlines = readList(incoming, "deadline", DEADLINE_IDS);
    const nextCountries = readCountries(incoming);
    setSeen(queryString);
    if (nextQ !== q) setQ(nextQ);
    if (!sameList(nextKinds, selected)) setSelected(nextKinds);
    if (!sameList(nextDeadlines, deadlines)) setDeadlines(nextDeadlines);
    if (!sameCountries(nextCountries, countries)) setCountries(nextCountries);
  } else if (seen !== queryString) {
    setSeen(queryString);
  }

  function commit(next: { q?: string; selected?: string[]; deadlines?: string[]; countries?: string[] | null }) {
    const query = next.q ?? q;
    const kinds = next.selected ?? selected;
    const dates = next.deadlines ?? deadlines;
    const places = next.countries === undefined ? countries : next.countries;
    if (next.q !== undefined) setQ(next.q);
    if (next.selected) setSelected(next.selected);
    if (next.deadlines) setDeadlines(next.deadlines);
    if (next.countries !== undefined) setCountries(next.countries);
    const serialized = searchQuery(query, kinds, dates, places);
    if (serialized === queryString) return;
    skipUrl.current = serialized;
    router.replace(serialized ? `/search?${serialized}` : "/search", { scroll: false });
  }

  useEffect(() => {
    const chosen = selectionKey ? selectionKey.split(",") : [];
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (countryKey !== "*" && countryKey !== "") {
      countryKey.split(",").forEach((value) => params.append("country", value));
    }
    if (chosen.length > 0 && chosen.length < KIND_IDS.length) {
      chosen.forEach((value) => params.append("kind", value));
    }
    const chosenDeadlines = deadlineKey ? deadlineKey.split(",") : [];
    if (chosenDeadlines.length > 0 && chosenDeadlines.length < DEADLINE_IDS.length) {
      chosenDeadlines.forEach((value) => params.append("deadline", value));
    }
    const handle = setTimeout(() => {
      setLoading(true);
      api<SearchResponse>(`/opportunities?${params.toString()}`)
        .then((body) => {
          setData(body);
          setError(null);
        })
        .catch((err: Error) => setError(err.message))
        .finally(() => setLoading(false));
    }, 200);
    return () => clearTimeout(handle);
  }, [q, selectionKey, countryKey, deadlineKey]);

  const countryOptions = [
    ...(data?.facets?.country || [])
      .map((row) => ({ id: row.value, name: countryLabel(row.value), count: row.count }))
      .sort((a, b) => a.name.localeCompare(b.name)),
    { id: "uncategorized", name: t("uncategorized"), count: data?.facets?.country_missing || 0 },
  ];
  const countrySelection = countries === null ? countryOptions.map((option) => option.id) : countries;
  const matches =
    countries?.length === 0 || selected.length === 0 || deadlines.length === 0 ? [] : (data?.items ?? []);
  const compareIds = useCompareIds();
  const items = matches.filter((item) => !compareIds.includes(item.id));
  const picking = compareIds.length > 0;
  const [previewId, setPreviewId] = useState<string | null>(null);

  return (
    <div className="space-y-10">
      {compareIds.length > 0 && <SelectedToCompare ids={compareIds} />}
      <section>
      <label className="block text-sm" htmlFor="q">
        Search
      </label>
      <input
        id="q"
        value={q}
        onChange={(event) => commit({ q: event.target.value })}
        placeholder={t("searchPlaceholder")}
        className="mt-1 w-full border border-border bg-background px-3 py-2 text-sm"
      />
      <div className="mt-4 flex flex-wrap items-center gap-3 text-sm">
        <MultiFilter
          name={t("country")}
          allLabel={t("allCountries")}
          emptyLabel={t("noCountries")}
          selected={countrySelection}
          onChange={(next) => commit({ countries: next.length === countryOptions.length ? null : next })}
          options={countryOptions}
        />
        <MultiFilter
          name={t("type")}
          allLabel={t("allTypes")}
          emptyLabel={t("noTypes")}
          selected={selected}
          onChange={(next) => commit({ selected: next })}
          options={KINDS.map(([id, label]) => ({
            id,
            name: label,
            count: data?.counts?.kind[id] || 0,
          }))}
        />
        <MultiFilter
          name={t("deadline")}
          allLabel={t("allDeadlines")}
          emptyLabel={t("noDeadlines")}
          selected={deadlines}
          onChange={(next) => commit({ deadlines: next })}
          options={DEADLINES.map(([id, label]) => ({
            id,
            name: t(label),
            count: data?.counts?.deadline?.[id] || 0,
          }))}
        />
      </div>
      {loading && <LoadingState label={t("loading")} className="mt-6" />}
      {error && <p className="mt-6 text-sm text-status-urgent">{t("error")}</p>}
      {!loading && matches.length === 0 && (
        <p className="mt-6 text-sm">{selected.length === 0 || deadlines.length === 0 ? t("empty") : data?.suggestion || t("empty")}</p>
      )}
      <ul className="mt-6 divide-y divide-border">
        {items?.map((item) => (
          <Row key={item.id} item={item} picking={picking} onOpen={setPreviewId} />
        ))}
      </ul>
    </section>
      {previewId && <CallPreview id={previewId} onClose={() => setPreviewId(null)} />}
    </div>
  );
}

const regionNames = new Intl.DisplayNames(["en"], { type: "region" });

function countryLabel(code: string): string {
  try {
    return regionNames.of(code) || code;
  } catch {
    return code;
  }
}

function MultiFilter({
  name,
  allLabel,
  emptyLabel,
  options,
  selected,
  onChange,
}: {
  name: string;
  allLabel: string;
  emptyLabel?: string;
  options: { id: string; name: string; count: number }[];
  selected: string[];
  onChange: (value: string[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const listId = useId();
  const allOn = options.length > 0 && selected.length === options.length;

  useEffect(() => {
    if (!open) return;
    function onPointer(event: MouseEvent) {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    function onOther(event: Event) {
      if ((event as CustomEvent<string>).detail !== listId) setOpen(false);
    }
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    window.addEventListener("multi-filter-open", onOther);
    window.dispatchEvent(new CustomEvent("multi-filter-open", { detail: listId }));
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("multi-filter-open", onOther);
    };
  }, [open, listId]);

  const summary = allOn
    ? allLabel
    : selected.length === 0
      ? emptyLabel || allLabel
      : options
          .filter((option) => selected.includes(option.id))
          .map((option) => option.name)
          .join(", ");

  function toggle(id: string) {
    onChange(selected.includes(id) ? selected.filter((item) => item !== id) : [...selected, id]);
  }

  return (
    <div ref={root} className="relative">
      <button
        type="button"
        aria-label={name}
        aria-expanded={open}
        aria-controls={listId}
        title={summary}
        onClick={() => setOpen((current) => !current)}
        className="max-w-64 cursor-pointer truncate border border-border bg-background px-2 py-1 text-left text-sm hover:bg-muted"
      >
        {summary}
      </button>
      {open && (
        <div id={listId} className="absolute left-0 z-20 mt-1 min-w-full border border-border bg-background p-2 shadow-sm">
          <label className="flex cursor-pointer items-center gap-2 whitespace-nowrap px-1 py-1">
            <input
              type="checkbox"
              checked={allOn}
              onChange={() => onChange(allOn ? [] : options.map((option) => option.id))}
            />
            <span>{allLabel}</span>
          </label>
          {options.map((option) => (
            <label key={option.id} className="flex cursor-pointer items-center gap-2 whitespace-nowrap px-1 py-1">
              <input
                type="checkbox"
                checked={selected.includes(option.id)}
                onChange={() => toggle(option.id)}
              />
              <span>
                {option.name} ({option.count})
              </span>
            </label>
          ))}
        </div>
      )}
    </div>
  );
}

function SelectedToCompare({ ids }: { ids: string[] }) {
  const key = ids.join(",");
  const [cards, setCards] = useState<Card[]>([]);
  useEffect(() => {
    const chosen = key.split(",").filter(Boolean);
    let cancel = false;
    Promise.all(chosen.map((id) => api<Card>(`/opportunities/${id}`)))
      .then((found) => {
        if (!cancel) setCards(found);
      })
      .catch(() => {
        if (!cancel) setCards([]);
      });
    return () => {
      cancel = true;
    };
  }, [key]);

  return (
    <section aria-label={t("comparing")} className="bg-accent-wash px-4 py-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-sm font-medium">{t("comparing")}</h2>
        {ids.length === 1 ? (
          <button type="button" className="cursor-pointer text-sm underline" onClick={() => toggleCompare(ids[0])}>
            {t("remove")}
          </button>
        ) : (
          <Link href={comparePath(ids)} className="inline-flex bg-primary px-3 py-1 text-sm text-primary-foreground">
            {t("compare")} ({ids.length})
          </Link>
        )}
      </div>
      <ul className="mt-3 divide-y divide-border border-t border-border">
        {ids.map((id) => cards.find((card) => card.id === id) ?? ({ id } as Card)).map((card) => (
          <li key={card.id} className="flex items-start justify-between gap-4 py-3">
            <div>
              {card.title && (
                <p className="font-mono text-xs text-muted-foreground">
                  {card.kind} · {card.programme_id || card.country || "—"}
                </p>
              )}
              <Link href={`/opportunities/${card.id}`} className="mt-1 block font-medium hover:underline">
                {card.title_en || card.title || t("loadingCall")}
              </Link>
            </div>
            {ids.length > 1 && (
              <button type="button" className="cursor-pointer text-sm underline" onClick={() => toggleCompare(card.id)}>
                {t("remove")}
              </button>
            )}
          </li>
        ))}
      </ul>
      {ids.length === 1 && <p className="mt-3 text-sm text-muted-foreground italic">{t("comparePick")}</p>}
    </section>
  );
}

function Row({ item, picking, onOpen }: { item: Card; picking: boolean; onOpen: (id: string) => void }) {
  const left = daysLeft(item.deadline_at);
  const urgent = left?.startsWith("Closes in") && Number(left.replace(/\D/g, "")) < 15;
  const title = item.title_en || item.title;
  return (
    <li className="grid grid-cols-[1fr_auto] gap-4 py-4">
      <div>
        <p className="font-mono text-xs text-muted-foreground">
          {item.kind} · {item.programme_id || item.country || "—"}
        </p>
        {picking ? (
          <button
            type="button"
            onClick={() => onOpen(item.id)}
            className="mt-1 block cursor-pointer text-left font-medium hover:underline"
          >
            {title}
          </button>
        ) : (
          <Link href={`/opportunities/${item.id}`} className="mt-1 block font-medium hover:underline">
            {title}
          </Link>
        )}
        {item.summary_en && <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{item.summary_en}</p>}
        {item.why && <p className="mt-1 text-xs text-muted-foreground">{item.why}</p>}
        {item.fit && <p className="mt-2 text-sm">{item.fit.line}</p>}
      </div>
      <div className="text-right">
        <p className={`tabular font-mono text-sm ${urgent ? "text-status-urgent" : "text-status-open"}`}>
          {left || item.status}
        </p>
        <p className="tabular font-mono text-xs text-muted-foreground">{when(item.deadline_at)}</p>
        <p className="tabular mt-2 font-mono text-sm">{money(item.budget_total_eur || item.amount_max_eur)}</p>
      </div>
    </li>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={<LoadingState label={t("loading")} className="mt-6" />}>
      <SearchScreen />
    </Suspense>
  );
}

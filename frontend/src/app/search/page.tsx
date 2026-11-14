"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useId, useRef, useState } from "react";
import { CallPreview } from "@/components/call-preview";
import { LoadingState } from "@/components/loading-state";
import { StatBox } from "@/components/stat-box";
import { api, type Card, type SearchResponse, type Stats } from "@/lib/api";
import { comparePath, toggleCompare, useCompareIds } from "@/lib/compare";
import { calendarDay, checkedAt, daysLeft, metaLine, moneyCompact, openOrUpcomingCount, shortTitle, shownBudget, when } from "@/lib/format";
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
  ["upcoming", "deadlineUpcoming"],
  ["closed", "deadlineClosed"],
] as const;

const DEADLINE_IDS = DEADLINES.map(([id]) => id);
const PAGE = 20;
// Upcoming stays out of the working list until someone asks for it.
const DEFAULT_DEADLINES = ["open", "closing_soon"];
const NONE = "none";

function readList(params: URLSearchParams, key: string, all: readonly string[]): string[] {
  const values = params.getAll(key);
  if (values.length === 0) return [...all];
  if (values.length === 1 && values[0] === NONE) return [];
  return values.filter((value) => all.includes(value));
}

function readDeadlines(params: URLSearchParams): string[] {
  const values = params.getAll("deadline");
  if (values.length === 0) return [...DEFAULT_DEADLINES];
  if (values.length === 1 && values[0] === NONE) return [];
  return values.filter((value) => (DEADLINE_IDS as readonly string[]).includes(value));
}

function writeDeadlines(params: URLSearchParams, selected: string[]) {
  if (selected.length === 0) {
    params.append("deadline", NONE);
    return;
  }
  const isDefault =
    selected.length === DEFAULT_DEADLINES.length && DEFAULT_DEADLINES.every((id) => selected.includes(id));
  if (isDefault) return;
  for (const id of DEADLINE_IDS) {
    if (selected.includes(id)) params.append("deadline", id);
  }
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

function searchQuery(
  q: string,
  kinds: string[],
  deadlines: string[],
  countries: string[] | null,
  wrappingUp: boolean,
): string {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  writeList(params, "kind", kinds, KIND_IDS);
  writeDeadlines(params, deadlines);
  writeCountries(params, countries);
  if (wrappingUp) params.set("wrapping_up", "1");
  return params.toString();
}

function sameList(left: string[], right: string[]): boolean {
  if (left.length !== right.length) return false;
  const a = [...left].sort();
  const b = [...right].sort();
  return a.every((value, index) => value === b[index]);
}

function resultQuery(
  offset: number,
  query: string,
  kindsKey: string,
  placesKey: string,
  datesKey: string,
  wrappingUp: boolean,
): string {
  const params = new URLSearchParams();
  if (query) params.set("q", query);
  if (wrappingUp) params.set("wrapping_up", "true");
  if (!wrappingUp && placesKey !== "*" && placesKey !== "") {
    placesKey.split(",").forEach((value) => params.append("country", value));
  }
  const chosen = kindsKey ? kindsKey.split(",") : [];
  if (!wrappingUp && chosen.length > 0 && chosen.length < KIND_IDS.length) {
    chosen.forEach((value) => params.append("kind", value));
  }
  const dates = datesKey ? datesKey.split(",") : [];
  if (!wrappingUp && dates.length > 0 && dates.length < DEADLINE_IDS.length) {
    dates.forEach((value) => params.append("deadline", value));
  }
  params.set("limit", String(PAGE));
  params.set("offset", String(offset));
  return params.toString();
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
  const [rows, setRows] = useState<Card[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [counts, setCounts] = useState<SearchResponse["counts"]>();
  const [facets, setFacets] = useState<SearchResponse["facets"]>();
  const [suggestion, setSuggestion] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [stats, setStats] = useState<Stats | null>(null);
  const [statsFailed, setStatsFailed] = useState(false);
  const [countries, setCountries] = useState<string[] | null>(() => readCountries(params));
  const [deadlines, setDeadlines] = useState<string[]>(() => readDeadlines(params));
  const [wrappingUp, setWrappingUp] = useState(() => params.get("wrapping_up") === "1");
  const [seen, setSeen] = useState(queryString);
  const selectionKey = [...selected].sort().join(",");
  const countryKey = countries === null ? "*" : [...countries].sort().join(",");
  const deadlineKey = [...deadlines].sort().join(",");
  const skipUrl = useRef(queryString);
  const request = useRef(0);
  const listRef = useRef<HTMLUListElement>(null);
  const focusId = useRef<string | null>(null);
  const figures = new Intl.NumberFormat("en");

  if (seen !== queryString && queryString !== skipUrl.current) {
    const incoming = new URLSearchParams(queryString);
    const nextQ = incoming.get("q") ?? "";
    const nextKinds = readList(incoming, "kind", KIND_IDS);
    const nextDeadlines = readDeadlines(incoming);
    const nextCountries = readCountries(incoming);
    const nextWrap = incoming.get("wrapping_up") === "1";
    setSeen(queryString);
    if (nextQ !== q) setQ(nextQ);
    if (!sameList(nextKinds, selected)) setSelected(nextKinds);
    if (!sameList(nextDeadlines, deadlines)) setDeadlines(nextDeadlines);
    if (!sameCountries(nextCountries, countries)) setCountries(nextCountries);
    if (nextWrap !== wrappingUp) setWrappingUp(nextWrap);
  } else if (seen !== queryString) {
    setSeen(queryString);
  }

  function commit(next: {
    q?: string;
    selected?: string[];
    deadlines?: string[];
    countries?: string[] | null;
    wrappingUp?: boolean;
  }) {
    const query = next.q ?? q;
    const kinds = next.selected ?? selected;
    const dates = next.deadlines ?? deadlines;
    const places = next.countries === undefined ? countries : next.countries;
    const wrap = next.wrappingUp ?? wrappingUp;
    if (next.q !== undefined) setQ(next.q);
    if (next.selected) setSelected(next.selected);
    if (next.deadlines) setDeadlines(next.deadlines);
    if (next.countries !== undefined) setCountries(next.countries);
    if (next.wrappingUp !== undefined) setWrappingUp(next.wrappingUp);
    const serialized = searchQuery(query, kinds, dates, places, wrap);
    if (serialized === queryString) return;
    skipUrl.current = serialized;
    router.replace(serialized ? `/search?${serialized}` : "/search", { scroll: false });
  }

  useEffect(() => {
    const id = ++request.current;
    const query = resultQuery(0, q, selectionKey, countryKey, deadlineKey, wrappingUp);
    const handle = setTimeout(() => {
      setLoading(true);
      setRows([]);
      setTotal(null);
      api<SearchResponse>(`/opportunities?${query}`)
        .then((body) => {
          if (request.current !== id) return;
          setRows(body.items);
          setTotal(body.total);
          setCounts(body.counts);
          setFacets(body.facets);
          setSuggestion(body.suggestion);
          setError(null);
        })
        .catch((err: Error) => {
          if (request.current !== id) return;
          setError(err.message);
        })
        .finally(() => {
          if (request.current !== id) return;
          setLoading(false);
        });
    }, 200);
    return () => clearTimeout(handle);
  }, [q, selectionKey, countryKey, deadlineKey, wrappingUp]);

  useEffect(() => {
    api<Stats>("/opportunities/stats")
      .then(setStats)
      .catch(() => setStatsFailed(true));
  }, []);

  useEffect(() => {
    const id = focusId.current;
    if (!id) return;
    focusId.current = null;
    listRef.current
      ?.querySelector<HTMLElement>(`[data-result-id="${id}"] a, [data-result-id="${id}"] button`)
      ?.focus();
  }, [rows]);

  function showMore() {
    const id = request.current;
    const offset = rows.length;
    setLoadingMore(true);
    api<SearchResponse>(
      `/opportunities?${resultQuery(offset, q, selectionKey, countryKey, deadlineKey, wrappingUp)}`,
    )
      .then((body) => {
        if (request.current !== id) return;
        setRows((current) => {
          const seen = new Set(current.map((row) => row.id));
          const extra = body.items.filter((row) => !seen.has(row.id));
          const next = [...current, ...extra];
          if (next.length >= body.total && extra[0]) focusId.current = extra[0].id;
          return next;
        });
        setTotal(body.total);
        setError(null);
      })
      .catch((err: Error) => {
        if (request.current !== id) return;
        setError(err.message);
      })
      .finally(() => {
        if (request.current !== id) return;
        setLoadingMore(false);
      });
  }

  const countryOptions = [
    ...(facets?.country || [])
      .map((row) => ({ id: row.value, name: countryLabel(row.value), count: row.count }))
      .sort((a, b) => a.name.localeCompare(b.name)),
    { id: "uncategorized", name: t("uncategorized"), count: facets?.country_missing || 0 },
  ].filter((option) => option.count > 0);
  const countrySelection = countries === null ? countryOptions.map((option) => option.id) : countries;
  const blocked =
    !wrappingUp && (countries?.length === 0 || selected.length === 0 || deadlines.length === 0);
  const matches = blocked ? [] : rows;
  const compareIds = useCompareIds();
  const items = matches.filter((item) => !compareIds.includes(item.id));
  const picking = compareIds.length > 0;
  const [previewId, setPreviewId] = useState<string | null>(null);
  const openNote =
    stats &&
    [
      stats.open_budget_eur > 0 ? t("statsBudget").replace("{amount}", moneyCompact(stats.open_budget_eur)) : null,
      stats.closing_soon > 0
        ? (stats.closing_soon === 1 ? t("statsClosingNoteOne") : t("statsClosingNote")).replace(
            "{count}",
            figures.format(stats.closing_soon),
          )
        : null,
    ]
      .filter(Boolean)
      .join(" · ");

  return (
    <div className="space-y-10">
      {compareIds.length > 0 && <SelectedToCompare ids={compareIds} />}
      <section>
      {!statsFailed && (
        <div className="mb-6 grid grid-cols-3 gap-3">
          <StatBox
            label={t("statsOpen")}
            value={stats ? figures.format(openOrUpcomingCount(stats)) : "—"}
            note={openNote || undefined}
            onClick={() =>
              commit({
                q: "",
                selected: [...KIND_IDS],
                countries: null,
                deadlines: stats && stats.upcoming > 0 ? [...DEFAULT_DEADLINES, "upcoming"] : [...DEFAULT_DEADLINES],
              })
            }
          />
          <StatBox
            label={t("statsWrapping")}
            value={stats ? figures.format(stats.wrapping_up ?? 0) : "—"}
            note={stats ? t("statsWrappingNote") : undefined}
            title={t("wrappingUpHint")}
            onClick={() => commit({ wrappingUp: !wrappingUp })}
          />
          {(!stats || stats.checked_at) && (
            <StatBox
              label={t("statsSources")}
              value={stats ? figures.format(stats.sources) : "—"}
              note={
                stats?.checked_at ? checkedAt(stats.checked_at) : undefined
              }
            />
          )}
        </div>
      )}
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
            {!wrappingUp && (
              <>
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
                count: counts?.kind?.[id] || 0,
              })).filter((option) => option.count > 0)}
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
                count: counts?.deadline?.[id] || 0,
              })).filter((option) => option.count > 0)}
            />
              </>
            )}
            <SingleFilter
              name={t("partners")}
              value={wrappingUp ? "wrapping" : "any"}
              onChange={(next) => commit({ wrappingUp: next === "wrapping" })}
              options={[
                { id: "any", name: t("partnersAny") },
                { id: "wrapping", name: t("partnersWrapping") },
              ]}
            />
      </div>
      {loading && <LoadingState label={t("loading")} className="mt-6" />}
      {error && <p className="mt-6 text-sm text-status-urgent">{t("error")}</p>}
      {!loading && total != null && total > 0 && !blocked && (
        <p className="mt-6 text-sm text-muted-foreground">
          {wrappingUp || rows.length < total
            ? t("showingOf").replace("{shown}", figures.format(rows.length)).replace("{total}", figures.format(total))
            : t("resultsCount").replace("{total}", figures.format(total))}
        </p>
      )}
      {!loading && matches.length === 0 && (
        <p className="mt-6 text-sm">
          {blocked ? t("empty") : suggestion || (wrappingUp ? t("wrappingUpEmpty") : t("empty"))}
        </p>
      )}
      <ul ref={listRef} className="mt-3 divide-y divide-border">
        {items?.map((item) => (
          <Row key={item.id} item={item} picking={picking} onOpen={setPreviewId} />
        ))}
      </ul>
      {!blocked && total != null && rows.length < total && (
        <button
          type="button"
          disabled={loadingMore}
          onClick={showMore}
          className="mt-4 cursor-pointer text-sm underline disabled:cursor-default disabled:no-underline"
        >
          {loadingMore ? t("showMoreLoading") : t("showMore")}
        </button>
      )}
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

function ChoiceBox({ checked, radio = false }: { checked: boolean; radio?: boolean }) {
  if (radio) {
    return (
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" className="size-4 shrink-0" aria-hidden>
        <path
          fill="currentColor"
          fillRule="evenodd"
          d={
            checked
              ? "M256 42.667c117.821 0 213.334 95.513 213.334 213.333c0 117.821-95.513 213.334-213.334 213.334c-117.82 0-213.333-95.513-213.333-213.334C42.667 138.18 138.18 42.667 256 42.667m0 42.667c-94.256 0-170.666 76.41-170.666 170.666c0 94.257 76.41 170.667 170.666 170.667c94.257 0 170.667-76.41 170.667-170.667c0-94.256-76.41-170.666-170.667-170.666m0 64c58.91 0 106.667 47.756 106.667 106.666S314.911 362.667 256 362.667c-58.91 0-106.666-47.756-106.666-106.667c0-58.91 47.756-106.666 106.666-106.666"
              : "M256 42.667c117.821 0 213.334 95.513 213.334 213.333c0 117.821-95.513 213.334-213.334 213.334c-117.82 0-213.333-95.513-213.333-213.334C42.667 138.18 138.18 42.667 256 42.667m0 42.667c-94.256 0-170.666 76.41-170.666 170.666c0 94.257 76.41 170.667 170.666 170.667c94.257 0 170.667-76.41 170.667-170.667c0-94.256-76.41-170.666-170.667-170.666"
          }
        />
      </svg>
    );
  }
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2"
      className="size-4 shrink-0"
      aria-hidden
    >
      {checked ? (
        <>
          <path d="M21 10.656V19a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h12.344" />
          <path d="m9 11 3 3L22 4" />
        </>
      ) : (
        <rect width="18" height="18" x="3" y="3" rx="2" />
      )}
    </svg>
  );
}

const choiceRow = "flex cursor-pointer items-center gap-2 whitespace-nowrap px-1 py-1 hover:bg-muted";

function SingleFilter({
  name,
  options,
  value,
  onChange,
}: {
  name: string;
  options: { id: string; name: string }[];
  value: string;
  onChange: (value: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const listId = useId();
  const group = useId();
  const summary = options.find((option) => option.id === value)?.name ?? name;

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

  return (
    <div ref={root} className="relative">
      <button
        type="button"
        aria-label={name}
        aria-expanded={open}
        aria-controls={listId}
        title={summary}
        onClick={() => setOpen((current) => !current)}
        className="cursor-pointer truncate border border-border bg-card px-2 py-1 text-left text-sm hover:bg-muted"
      >
        {summary}
      </button>
      {open && (
        <div id={listId} className="absolute left-0 z-20 mt-1 min-w-full border border-border bg-card p-2 shadow-sm">
          {options.map((option) => (
            <label key={option.id} className={choiceRow}>
              <input
                type="radio"
                name={group}
                checked={value === option.id}
                onChange={() => {
                  onChange(option.id);
                  setOpen(false);
                }}
                className="sr-only"
              />
              <ChoiceBox radio checked={value === option.id} />
              <span>{option.name}</span>
            </label>
          ))}
        </div>
      )}
    </div>
  );
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
  const allOn = options.length === 0 || options.every((option) => selected.includes(option.id));

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
        className="max-w-64 cursor-pointer truncate border border-border bg-card px-2 py-1 text-left text-sm hover:bg-muted"
      >
        {summary}
      </button>
      {open && (
        <div id={listId} className="absolute left-0 z-20 mt-1 min-w-full border border-border bg-card p-2 shadow-sm">
          <label className={choiceRow}>
            <input
              type="checkbox"
              checked={allOn}
              onChange={() => onChange(allOn ? [] : options.map((option) => option.id))}
              className="sr-only"
            />
            <ChoiceBox checked={allOn} />
            <span>{allLabel}</span>
          </label>
          {options.map((option) => (
            <label key={option.id} className={choiceRow}>
              <input
                type="checkbox"
                checked={selected.includes(option.id)}
                onChange={() => toggle(option.id)}
                className="sr-only"
              />
              <ChoiceBox checked={selected.includes(option.id)} />
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
                  {metaLine(card.kind, card.programme_id || card.country)}
                </p>
              )}
              <Link href={`/opportunities/${card.id}`} className="mt-1 block font-medium hover:underline">
                {shortTitle(card.title, card.title_en) || t("loadingCall")}
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
  const upcoming = item.notice === "pin";
  const left = upcoming ? null : daysLeft(item.deadline_at);
  const urgent = left?.startsWith("Closes in") && Number(left.replace(/\D/g, "")) < 15;
  const title = shortTitle(item.title, item.title_en);
  const whenLabel = item.deadline_at
    ? when(item.deadline_at)
    : upcoming
      ? calendarDay(item.published_at)
      : when(item.deadline_at);
  return (
    <li data-result-id={item.id} className="grid grid-cols-[1fr_auto] gap-4 py-4">
      <div>
        <p className="font-mono text-xs text-muted-foreground">
          {metaLine(item.kind, item.programme_id || item.country)}
          {upcoming && <span className="ml-2 text-status-open">{t("deadlineUpcoming")}</span>}
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
        {item.wrapping_up != null && item.wrapping_up > 0 && (
          <p className="mt-1 font-mono text-xs text-accent-ink">
            {(item.wrapping_up === 1 ? t("wrappingUpChipOne") : t("wrappingUpChip")).replace(
              "{count}",
              String(item.wrapping_up),
            )}
          </p>
        )}
        {item.why && <p className="mt-1 text-xs text-muted-foreground">{item.why}</p>}
        {item.fit && <p className="mt-2 text-sm">{item.fit.line}</p>}
      </div>
      <div className="text-right">
        <p className={`tabular font-mono text-sm ${urgent ? "text-status-urgent" : "text-status-open"}`}>
          {upcoming ? t("deadlineUpcoming") : left || item.status}
        </p>
        <p className="tabular font-mono text-xs text-muted-foreground">{whenLabel}</p>
        <p className="tabular mt-2 font-mono text-sm">
          {shownBudget(item.budget_total_eur || item.amount_max_eur, item.budget_amount, item.budget_currency)}
        </p>
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

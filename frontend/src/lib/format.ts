import { t } from "@/lib/i18n";

export function money(value: number | null | undefined): string {
  if (value == null) return "—";
  return moneyOf(value, "EUR");
}

export function moneyOf(amount: number | null | undefined, currency: string | null | undefined): string {
  if (amount == null) return "—";
  const code = (currency || "EUR").toUpperCase();
  try {
    return new Intl.NumberFormat("en", {
      style: "currency",
      currency: code,
      maximumFractionDigits: 0,
    }).format(amount);
  } catch {
    return `${code} ${Math.round(amount).toLocaleString("en")}`;
  }
}

export function shownBudget(
  eur: number | null | undefined,
  amount?: number | null,
  currency?: string | null,
): string {
  if (eur != null) return money(eur);
  if (amount != null && currency && currency.toUpperCase() !== "EUR") return moneyOf(amount, currency);
  if (amount != null) return moneyOf(amount, currency || "EUR");
  return "—";
}

/** A calendar date, not a timestamp. `2026-11-13` stays that day in any timezone. */
export function calendarDay(iso: string | null | undefined): string {
  if (!iso) return "No date published";
  const [year, month, day] = iso.slice(0, 10).split("-").map(Number);
  if (!year || !month || !day) return "No date published";
  return new Intl.DateTimeFormat("en", { dateStyle: "medium" }).format(new Date(year, month - 1, day));
}

export function openOrUpcomingCount(stats: { open: number; closing_soon: number; upcoming?: number }): number {
  return stats.open + stats.closing_soon + (stats.upcoming ?? 0);
}

export const openOrUpcomingHref = "/search?deadline=open&deadline=closing_soon&deadline=upcoming";

export function when(iso: string | null | undefined): string {
  if (!iso) return "No date published";
  const date = new Date(iso);
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function metaLine(...parts: (string | null | undefined)[]): string {
  return parts.filter(Boolean).join(" · ");
}

export function shortTitle(title: string | null | undefined, titleEn: string | null | undefined): string {
  const english = (titleEn || "").trim();
  const original = (title || "").trim();
  if (!english) return original;
  // TED's English title is "Country – CPV label – original title". The label is not the call.
  if (original && english !== original && english.endsWith(original)) return original;
  return english;
}

export function moneyCompact(value: number): string {
  return new Intl.NumberFormat("en", {
    style: "currency",
    currency: "EUR",
    notation: "compact",
    maximumFractionDigits: 0,
  }).format(value);
}

export function checkedAt(iso: string): string {
  const date = new Date(iso);
  const elapsed = Date.now() - date.getTime();
  if (Number.isNaN(date.getTime()) || elapsed < 60_000) return t("statsCheckedNow");
  const minutes = Math.floor(elapsed / 60_000);
  if (minutes < 60) {
    const key = minutes === 1 ? "statsCheckedMinuteOne" : "statsCheckedMinutes";
    return t(key).replace("{count}", String(minutes));
  }
  const hours = Math.floor(elapsed / 3_600_000);
  if (hours < 24) {
    const key = hours === 1 ? "statsCheckedHourOne" : "statsCheckedHours";
    return t(key).replace("{count}", String(hours));
  }
  const days = Math.floor(hours / 24);
  const key = days === 1 ? "statsCheckedDayOne" : "statsCheckedDays";
  return t(key).replace("{count}", String(days));
}

export function daysLeft(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const ms = new Date(iso).getTime() - Date.now();
  const days = Math.ceil(ms / 86_400_000);
  if (days < 0) return "Closed";
  if (days === 0) return "Closes today";
  return `Closes in ${days} days`;
}

import type { Card, SearchResponse } from "@/lib/api";
import { metaLine, money, shortTitle } from "@/lib/format";
import { t } from "@/lib/i18n";

export type LandingCall = Card & { relevance?: number | null };

export type LandingSearch = Omit<SearchResponse, "items"> & { items: LandingCall[] };

const SHOWCASE = 6;
const MIN_RELEVANCE = 0.5;

const figures = new Intl.NumberFormat("en");

export function landingCount(value: number): string {
  return figures.format(value);
}

function positive(value: number | null | undefined): number | null {
  if (value == null || value <= 0) return null;
  return value;
}

/** 0 is missing data. `budget_total_eur || amount_max_eur` would print €0. */
export function landingMoney(eur: number | null | undefined, maxEur: number | null | undefined): string {
  const amount = positive(eur) ?? positive(maxEur);
  if (amount == null) return "—";
  return money(amount);
}

function calendarDaysUntil(iso: string): number | null {
  const deadline = new Date(iso);
  if (Number.isNaN(deadline.getTime())) return null;
  const now = new Date();
  const day = (date: Date) => Date.UTC(date.getFullYear(), date.getMonth(), date.getDate());
  return Math.round((day(deadline) - day(now)) / 86_400_000);
}

/** Calendar days, not a ceil of the remaining milliseconds. Today stays "today". */
export function landingDeadline(iso: string | null | undefined): { label: string | null; urgent: boolean } {
  if (!iso) return { label: null, urgent: false };
  const days = calendarDaysUntil(iso);
  if (days == null) return { label: null, urgent: false };
  if (days < 0) return { label: t("landingClosed"), urgent: false };
  if (days === 0) return { label: t("landingClosesToday"), urgent: true };
  const key = days === 1 ? "landingClosesInOne" : "landingClosesIn";
  return { label: t(key).replace("{count}", landingCount(days)), urgent: days < 15 };
}

/** The call title. TED's English prefix is dropped in `shortTitle`. */
export function landingTitle(title: string | null | undefined, titleEn: string | null | undefined): string {
  return shortTitle(title, titleEn);
}

export function landingMeta(
  kind: string | null | undefined,
  programmeId: string | null | undefined,
  country: string | null | undefined,
): string {
  const label = kind
    ? kind
        .split("_")
        .filter(Boolean)
        .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
        .join(" ")
    : null;
  return metaLine(label, programmeId || country);
}

/** First multi-word keyword without a wildcard. Search treats it as a sector concept. */
export function sectorQuery(keywords: string[] | undefined): string | null {
  for (const keyword of keywords || []) {
    const trimmed = keyword.trim();
    if (!trimmed || trimmed.includes("*")) continue;
    if (trimmed.split(/\s+/).length >= 2) return trimmed;
  }
  return null;
}

/** The six calls the landing shows: still open, not a low-confidence text hit, and not a duplicate. */
export function landingShowcase(items: LandingCall[]): LandingCall[] {
  const now = Date.now();
  const seen = new Set<string>();
  const picked: LandingCall[] = [];
  for (const item of items) {
    if (item.deadline_at) {
      const at = new Date(item.deadline_at).getTime();
      if (!Number.isNaN(at) && at < now) continue;
    }
    if (typeof item.relevance === "number" && item.relevance < MIN_RELEVANCE) continue;
    const key = [landingTitle(item.title, item.title_en), item.country ?? "", item.deadline_at ?? ""].join("\0");
    if (seen.has(key)) continue;
    seen.add(key);
    picked.push(item);
    if (picked.length === SHOWCASE) break;
  }
  return picked;
}

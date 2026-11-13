export function money(value: number | null | undefined): string {
  if (value == null) return "—";
  return new Intl.NumberFormat("en", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(value);
}

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
  if (!original || english === original || !english.endsWith(original)) return english;
  return english.slice(0, english.length - original.length).replace(/[\s–—-]+$/u, "") || english;
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
  const now = new Date();
  const sameDay =
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate();
  if (sameDay) {
    const time = new Intl.DateTimeFormat("en", {
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    }).format(date);
    return `today, ${time}`;
  }
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric" }).format(date);
}

export function daysLeft(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const ms = new Date(iso).getTime() - Date.now();
  const days = Math.ceil(ms / 86_400_000);
  if (days < 0) return "Closed";
  if (days === 0) return "Closes today";
  return `Closes in ${days} days`;
}

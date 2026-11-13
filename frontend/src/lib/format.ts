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

export function daysLeft(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const ms = new Date(iso).getTime() - Date.now();
  const days = Math.ceil(ms / 86_400_000);
  if (days < 0) return "Closed";
  if (days === 0) return "Closes today";
  return `Closes in ${days} days`;
}

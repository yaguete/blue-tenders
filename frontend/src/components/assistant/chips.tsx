"use client";

import { X } from "lucide-react";
import { t } from "@/lib/i18n";
import type { DocChip } from "@/lib/assistant-chat";

export function shown(doc: { kind?: string | null; access?: string | null; status?: string | null; name?: string | null }): boolean {
  // El texto del topic y los enlaces de la ficha ya están a la vista. La pastilla es para un PDF u otro archivo que el asistente lee y la página no enseña.
  if (doc.kind === "topic_text" || doc.access === "link_only" || doc.status === "link_only") return false;
  if (doc.name === "Topic page" || doc.name === "Partner search") return false;
  return true;
}

function label(doc: DocChip): string {
  const name = doc.name || "Document";
  if (doc.status === "fetching") return `${name} · ${t("assistantThinking")}`;
  if (doc.status === "failed") return `${name} · couldn't read`;
  if (doc.status === "too_large") return `${name} · too large`;
  const pages = doc.pages ? ` · ${doc.pages} ${doc.pages === 1 ? "page" : "pages"}` : "";
  return `${name}${pages}`;
}

export function Chips({
  documents,
  uploads,
  onRemove,
}: {
  documents: DocChip[];
  uploads: DocChip[];
  onRemove: (id: string) => void;
}) {
  const items = [...documents.filter(shown), ...uploads];
  if (!items.length) return null;
  return (
    <ul className="mb-2 flex flex-wrap gap-1.5">
      {items.map((doc) => {
        const text = label(doc);
        const tone = doc.removable
          ? "bg-[oklch(0.95_0.02_250)] dark:bg-[oklch(0.26_0.03_250)]"
          : "bg-accent-wash";
        return (
          <li key={doc.id || doc.url || text}>
            <span className={`inline-flex items-center gap-2 px-2 py-1 text-xs ${tone}`}>
              {text}
              {doc.removable && doc.id && (
                <button type="button" aria-label={t("assistantRemove")} onClick={() => onRemove(doc.id!)}>
                  <X className="h-3 w-3" />
                </button>
              )}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

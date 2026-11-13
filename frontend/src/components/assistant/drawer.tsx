"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { MessageCircle } from "lucide-react";
import { usePathname, useSearchParams } from "next/navigation";
import { API_URL } from "@/lib/api";
import { t } from "@/lib/i18n";
import { useAssistantChat } from "@/lib/assistant-chat";
import { Panel } from "./panel";
import { shown } from "./chips";

function suggestionsFor(pathname: string | null): string[] {
  if (pathname?.startsWith("/opportunities/")) {
    return [
      "What is the deadline?",
      "Who can apply, according to the text?",
      "What is the co-funding rate?",
      "Where is the official call?",
    ];
  }
  if (pathname?.startsWith("/funders")) {
    return ["What does the EIB fund?", "Which funders offer loans?"];
  }
  return ["What is a consortium in Horizon Europe?", "What calls close in the next two months?"];
}

export function Assistant() {
  const pathname = usePathname();
  const params = useSearchParams();
  const opportunityId = pathname?.match(/^\/opportunities\/([^/]+)/)?.[1] ?? null;
  const chat = useAssistantChat(opportunityId);
  const { open, setOpen } = chat;
  const pillRef = useRef<HTMLButtonElement>(null);
  const [listed, setListed] = useState(0);
  const returnFocus = useCallback(() => pillRef.current?.focus(), []);

  useEffect(() => {
    if (!opportunityId) {
      setListed(0);
      return;
    }
    let cancel = false;
    fetch(`${API_URL}/opportunities/${opportunityId}`)
      .then((response) => (response.ok ? response.json() : null))
      .then((body) => {
        if (!cancel && body) setListed((body.documents || []).filter(shown).length);
      })
      .catch(() => {
        if (!cancel) setListed(0);
      });
    return () => {
      cancel = true;
    };
  }, [opportunityId]);

  useEffect(() => {
    if (params.get("ask") === "1") setOpen(true);
  }, [params, setOpen]);

  useEffect(() => {
    function openPanel() {
      setOpen(true);
    }
    window.addEventListener("assistant-open", openPanel);
    return () => window.removeEventListener("assistant-open", openPanel);
  }, [setOpen]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key !== "a" || event.metaKey || event.ctrlKey || event.altKey || open) return;
      const tag = (event.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || (event.target as HTMLElement | null)?.isContentEditable) return;
      event.preventDefault();
      setOpen(true);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, setOpen]);

  const pill =
    opportunityId && listed
      ? `${t("assistantAskCall")} · ${listed === 1 ? t("assistantDocumentOne") : t("assistantDocuments").replace("{count}", String(listed))}`
      : opportunityId
        ? t("assistantAskCall")
        : t("assistantAsk");

  return (
    <>
      {chat.open && (
        <button
          type="button"
          aria-label={t("assistantClose")}
          className="fixed inset-0 z-40 bg-foreground/10"
          onClick={() => chat.setOpen(false)}
        />
      )}
      {chat.open && (
        <div className="fixed inset-0 z-50 sm:inset-auto sm:bottom-20 sm:left-1/2 sm:h-[min(680px,82vh)] sm:w-[420px] sm:-translate-x-1/2 sm:shadow-xl sm:shadow-foreground/20">
          <Panel
            messages={chat.messages}
            documents={chat.documents}
            uploads={chat.uploads}
            busy={chat.busy}
            error={chat.error}
            draft={chat.draft}
            mismatch={chat.mismatch}
            suggestions={suggestionsFor(pathname)}
            onDraft={chat.setDraft}
            onSend={chat.send}
            onClose={() => chat.setOpen(false)}
            onReset={chat.reset}
            onUpload={chat.addUpload}
            onRemove={chat.removeUpload}
            returnFocus={returnFocus}
          />
        </div>
      )}
      {!chat.open && (
        <button
          ref={pillRef}
          type="button"
          className="fixed bottom-4 left-1/2 z-40 flex -translate-x-1/2 cursor-pointer items-center gap-2 border border-foreground bg-[oklch(0.94_0_0)] px-4 py-2.5 text-sm text-foreground shadow-lg shadow-foreground/10 transition-transform duration-200 hover:scale-105 motion-reduce:transition-none motion-reduce:hover:scale-100 dark:bg-[oklch(0.28_0_0)] dark:text-white"
          onClick={() => chat.setOpen(true)}
        >
          <MessageCircle className="h-4 w-4" />
          {pill}
        </button>
      )}
    </>
  );
}

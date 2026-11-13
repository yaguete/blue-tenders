"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";
import { ArrowUp, Plus, Square, SquarePen, X } from "lucide-react";
import { t } from "@/lib/i18n";
import type { ChatMessage, DocChip } from "@/lib/assistant-chat";
import { Chips } from "./chips";
import { Loading } from "./loading";
import { Message } from "./message";

export function Panel({
  messages,
  documents,
  uploads,
  busy,
  status,
  revealing,
  announced,
  error,
  draft,
  mismatch,
  subject,
  previousTitle,
  suggestions,
  onDraft,
  onSend,
  onStop,
  onClose,
  onReset,
  onRestore,
  onUpload,
  onRemove,
  returnFocus,
}: {
  messages: ChatMessage[];
  documents: DocChip[];
  uploads: DocChip[];
  busy: boolean;
  status: string | null;
  revealing: boolean;
  announced: string;
  error: string | null;
  draft: string;
  mismatch: boolean;
  subject: string | null;
  previousTitle: string | null;
  suggestions: string[];
  onDraft: (value: string) => void;
  onSend: (text: string) => void;
  onStop: () => void;
  onClose: () => void;
  onReset: () => void;
  onRestore: () => void;
  onUpload: (file: File) => void;
  onRemove: (id: string) => void;
  returnFocus: () => void;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const stickRef = useRef(true);
  const onCloseRef = useRef(onClose);
  const returnFocusRef = useRef(returnFocus);
  onCloseRef.current = onClose;
  returnFocusRef.current = returnFocus;

  useEffect(() => {
    const root = panelRef.current;
    if (!root) return;
    const dialog = root;
    inputRef.current?.focus();
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab") return;
      const items = [...dialog.querySelectorAll<HTMLElement>("button, textarea, a, input")].filter(
        (node) => !node.hasAttribute("disabled"),
      );
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      returnFocusRef.current();
    };
  }, []);

  useEffect(() => {
    stickRef.current = true;
  }, [messages.length]);

  useEffect(() => {
    if (!stickRef.current) return;
    const node = panelRef.current?.querySelector("[data-assistant-scroll]");
    if (node) node.scrollTop = node.scrollHeight;
  }, [messages, busy, revealing]);

  useEffect(() => {
    const node = inputRef.current;
    if (!node) return;
    node.style.height = "auto";
    node.style.height = `${node.scrollHeight}px`;
  }, [draft]);

  const last = messages[messages.length - 1];
  const showLoading = busy && !(last?.role === "assistant" && last.text);
  const liveId =
    busy || revealing
      ? [...messages].reverse().find((message) => message.role === "assistant")?.id
      : undefined;

  return (
    <div
      ref={panelRef}
      role="dialog"
      aria-modal="true"
      aria-labelledby="assistant-title"
      className="flex h-full min-h-0 flex-col border border-border bg-background motion-reduce:transition-none"
    >
      <header className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
        <div className="min-w-0">
          <p id="assistant-title" className="text-sm font-medium">
            {t("assistantTitle")}
          </p>
          <p className="truncate text-xs text-muted-foreground">{subject || t("assistantAllCalls")}</p>
        </div>
        <div className="flex items-center gap-2">
          {messages.length > 0 && (
            <button
              type="button"
              onClick={onReset}
              aria-label={t("assistantNew")}
              className="flex h-8 w-8 cursor-pointer items-center justify-center text-muted-foreground hover:bg-muted"
            >
              <SquarePen className="h-4 w-4" />
            </button>
          )}
          <button
            type="button"
            onClick={onClose}
            className="flex h-8 w-8 cursor-pointer items-center justify-center text-muted-foreground hover:bg-muted"
            aria-label={t("assistantClose")}
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </header>
      {previousTitle && (
        <p className="px-4 pt-2 text-xs text-muted-foreground">
          <button type="button" className="underline" onClick={onRestore}>
            {t("assistantPrevious").replace("{title}", previousTitle)}
          </button>
        </p>
      )}
      {mismatch && (
        <p className="px-4 pb-2 text-xs text-muted-foreground">
          <button type="button" className="underline" onClick={onReset}>
            {t("assistantSwitch")}
          </button>
        </p>
      )}
      <div className="sr-only" aria-live="polite">
        {announced}
      </div>
      <div
        data-assistant-scroll
        className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-3"
        onScroll={(event) => {
          const node = event.currentTarget;
          stickRef.current = node.scrollHeight - node.scrollTop - node.clientHeight < 48;
        }}
      >
        {messages.length === 0 ? (
          <div className="flex h-full flex-col justify-end gap-3">
            <p className="text-sm text-muted-foreground">{t("assistantEmpty")}</p>
            <div className="flex flex-wrap gap-2">
              {suggestions.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  className="cursor-pointer border border-border px-2 py-1 text-left text-xs hover:bg-muted"
                  onClick={() => onSend(suggestion)}
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((message) => (
            <Message key={message.id} message={message} live={message.id === liveId && Boolean(message.text)} />
          ))
        )}
        {showLoading && <Loading status={status} />}
        {error === "sign-in" && (
          <p className="text-sm">
            {t("assistantSignIn")}{" "}
            <Link href="/profile" className="underline">
              {t("assistantSignInLink")}
            </Link>
          </p>
        )}
        {error === "closed" && <p className="text-sm">{t("assistantClosed")}</p>}
        {error === "quota" && <p className="text-sm">{t("assistantQuota")}</p>}
        {error === "paused" && <p className="text-sm">{t("assistantPaused")}</p>}
        {error === "error" && <p className="text-sm text-status-urgent">{t("assistantError")}</p>}
      </div>
      <form
        className="border-t border-border px-4 py-3"
        onSubmit={(event) => {
          event.preventDefault();
          onSend(draft);
        }}
      >
        <Chips documents={documents} uploads={uploads} onRemove={onRemove} />
        <div className="border border-border px-1.5 py-1">
          <textarea
            ref={inputRef}
            value={draft}
            onChange={(event) => onDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                onSend(draft);
              }
            }}
            rows={1}
            placeholder={t("assistantPlaceholder")}
            className="max-h-32 min-h-8 w-full resize-none overflow-y-auto bg-transparent px-1 py-1.5 text-sm leading-5 outline-none"
          />
          <div className="flex items-center justify-between gap-1">
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.txt,.md,application/pdf,text/plain"
              className="hidden"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) onUpload(file);
                event.target.value = "";
              }}
            />
            <button
              type="button"
              className="flex cursor-pointer items-center gap-1 px-1 py-1 text-xs font-normal leading-4 text-muted-foreground hover:text-foreground"
              onClick={() => fileRef.current?.click()}
            >
              <Plus className="h-3 w-3" />
              {t("assistantUpload")}
            </button>
            {busy ? (
              <button
                type="button"
                onClick={onStop}
                aria-label={t("assistantStop")}
                className="flex h-8 w-8 shrink-0 cursor-pointer items-center justify-center bg-primary text-primary-foreground"
              >
                <Square className="h-3.5 w-3.5 fill-current" />
              </button>
            ) : (
              <button
                type="submit"
                disabled={!draft.trim()}
                aria-label={t("assistantSend")}
                className="flex h-8 w-8 shrink-0 cursor-pointer items-center justify-center bg-primary text-primary-foreground disabled:cursor-default disabled:opacity-40"
              >
                <ArrowUp className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">{t("assistantUploadNotice")}</p>
      </form>
    </div>
  );
}

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { API_URL } from "@/lib/api";

export type Citation = {
  url?: string | null;
  label?: string | null;
  page?: number | null;
  heading?: string | null;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  citations?: Citation[];
};

export type DocChip = {
  id?: string;
  name: string | null;
  url?: string | null;
  status: string;
  pages?: number;
  access?: string | null;
  kind?: string | null;
  shared?: boolean;
  removable?: boolean;
};

type Stored = {
  conversationId: string | null;
  opportunityId: string | null;
  messages: ChatMessage[];
  uploads: DocChip[];
};

const STORAGE_KEY = "blue-tender-assistant";
const REVEAL_MS = 48;
const GUEST_KEY = "assistant-guest";

function guestId(): string {
  const current = window.localStorage.getItem(GUEST_KEY);
  if (current) return current;
  const created = crypto.randomUUID();
  window.localStorage.setItem(GUEST_KEY, created);
  return created;
}

function authHeaders(): Headers {
  const value = new Headers();
  const demo = window.localStorage.getItem("demo-user");
  if (demo) value.set("X-Demo-User", demo);
  value.set("X-Assistant-Guest", guestId());
  return value;
}

function aborted(err: unknown): boolean {
  return typeof err === "object" && err !== null && "name" in err && (err as { name: string }).name === "AbortError";
}

function deviceToday(): { today: string; timezone: string } {
  const now = new Date();
  const today = [
    now.getFullYear(),
    String(now.getMonth() + 1).padStart(2, "0"),
    String(now.getDate()).padStart(2, "0"),
  ].join("-");
  let timezone = "";
  try {
    timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || "";
  } catch {
    timezone = "";
  }
  return { today, timezone };
}

function headers(): Headers {
  const value = authHeaders();
  value.set("Content-Type", "application/json");
  return value;
}

function load(): Stored {
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return { conversationId: null, opportunityId: null, messages: [], uploads: [] };
    const parsed = JSON.parse(raw) as Stored;
    return {
      conversationId: parsed.conversationId ?? null,
      opportunityId: parsed.opportunityId ?? null,
      messages: Array.isArray(parsed.messages) ? parsed.messages : [],
      uploads: Array.isArray(parsed.uploads) ? parsed.uploads : [],
    };
  } catch {
    return { conversationId: null, opportunityId: null, messages: [], uploads: [] };
  }
}

type Archive = {
  conversationId: string | null;
  opportunityId: string | null;
  title: string | null;
  messages: ChatMessage[];
};

export function useAssistantChat(opportunityId: string | null, pageTitle: string | null = null) {
  const [open, setOpen] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [boundOpportunity, setBoundOpportunity] = useState<string | null>(null);
  const [boundTitle, setBoundTitle] = useState<string | null>(null);
  const [archive, setArchive] = useState<Archive | null>(null);
  const switched = useRef(false);
  const hold = useRef(false);
  const [uploads, setUploads] = useState<DocChip[]>([]);
  const [documents, setDocuments] = useState<DocChip[]>([]);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [revealing, setRevealing] = useState(false);
  const [announced, setAnnounced] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const stopRef = useRef(false);
  const busyRef = useRef(false);
  const timerRef = useRef<number | null>(null);
  const targetRef = useRef<Record<string, string>>({});
  const shownRef = useRef<Record<string, string>>({});
  const pumpRef = useRef<() => void>(() => {});

  useEffect(
    () => () => {
      if (timerRef.current != null) window.clearTimeout(timerRef.current);
    },
    [],
  );

  pumpRef.current = () => {
    if (stopRef.current) {
      setRevealing(false);
      return;
    }
    const updates: Record<string, string> = {};
    let still = false;
    for (const [id, target] of Object.entries(targetRef.current)) {
      const shown = shownRef.current[id] ?? "";
      if (shown === target) continue;
      if (!target.startsWith(shown)) {
        shownRef.current[id] = target;
        updates[id] = target;
        continue;
      }
      const lag = target.length - shown.length;
      const step = lag > 120 ? 2 : 1;
      const next = target.slice(0, shown.length + step);
      shownRef.current[id] = next;
      updates[id] = next;
      if (next.length < target.length) still = true;
    }
    if (Object.keys(updates).length) {
      setMessages((current) =>
        current.map((item) => (updates[item.id] != null ? { ...item, text: updates[item.id] } : item)),
      );
    }
    if (still && !stopRef.current) {
      setRevealing(true);
      timerRef.current = window.setTimeout(() => {
        timerRef.current = null;
        pumpRef.current();
      }, REVEAL_MS);
      return;
    }
    setRevealing(false);
    if (!busyRef.current) {
      const ids = Object.keys(targetRef.current);
      const last = ids[ids.length - 1];
      if (last) setAnnounced(targetRef.current[last] ?? "");
    }
  };

  const scheduleReveal = useCallback(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced || stopRef.current || timerRef.current != null) return;
    setRevealing(true);
    timerRef.current = window.setTimeout(() => {
      timerRef.current = null;
      pumpRef.current();
    }, REVEAL_MS);
  }, []);

  const pushText = useCallback(
    (id: string, extra: string) => {
      if (stopRef.current) return;
      const target = (targetRef.current[id] ?? "") + extra;
      targetRef.current[id] = target;
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        shownRef.current[id] = target;
        setMessages((current) => current.map((item) => (item.id === id ? { ...item, text: target } : item)));
        return;
      }
      if (shownRef.current[id] == null) shownRef.current[id] = "";
      scheduleReveal();
    },
    [scheduleReveal],
  );

  const clearText = useCallback((id: string) => {
    targetRef.current[id] = "";
    shownRef.current[id] = "";
    setMessages((current) => current.map((item) => (item.id === id ? { ...item, text: "" } : item)));
  }, []);

  useEffect(() => {
    const stored = load();
    setMessages(stored.messages);
    setConversationId(stored.conversationId);
    setBoundOpportunity(stored.opportunityId);
    setUploads(stored.uploads);
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    const payload: Stored = {
      conversationId,
      opportunityId: boundOpportunity,
      messages,
      uploads,
    };
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  }, [hydrated, conversationId, boundOpportunity, messages, uploads]);

  const refreshDocuments = useCallback(async () => {
    if (!opportunityId) {
      setDocuments([]);
      return;
    }
    const response = await fetch(`${API_URL}/assistant/context?opportunity_id=${opportunityId}`);
    if (!response.ok) return;
    const body = (await response.json()) as { documents: DocChip[] };
    setDocuments(body.documents || []);
  }, [opportunityId]);

  useEffect(() => {
    if (!opportunityId) {
      setDocuments([]);
      return;
    }
    if (!open) return;
    let stop = false;
    let tries = 0;
    async function tick() {
      await refreshDocuments();
      tries += 1;
    }
    tick();
    const timer = window.setInterval(() => {
      if (stop || tries > 15) {
        window.clearInterval(timer);
        return;
      }
      tick();
    }, 2000);
    return () => {
      stop = true;
      window.clearInterval(timer);
    };
  }, [open, opportunityId, refreshDocuments]);

  const reset = useCallback(() => {
    hold.current = false;
    setArchive(null);
    setMessages([]);
    setConversationId(null);
    setBoundOpportunity(opportunityId);
    setBoundTitle(pageTitle);
    setUploads([]);
    setError(null);
  }, [opportunityId, pageTitle]);

  const send = useCallback(
    async (text: string) => {
      const question = text.trim();
      if (!question || busy) return;
      setError(null);
      setDraft("");
      setStatus(null);
      setAnnounced("");
      stopRef.current = false;
      const mine: ChatMessage = { id: crypto.randomUUID(), role: "user", text: question };
      const reply: ChatMessage = { id: crypto.randomUUID(), role: "assistant", text: "", citations: [] };
      targetRef.current[reply.id] = "";
      shownRef.current[reply.id] = "";
      setMessages((current) => [...current, mine, reply]);
      busyRef.current = true;
      setBusy(true);
      const controller = new AbortController();
      abortRef.current = controller;
      if (!boundOpportunity) {
        setBoundOpportunity(opportunityId);
        setBoundTitle(pageTitle);
      }
      try {
        const response = await fetch(`${API_URL}/assistant`, {
          method: "POST",
          headers: headers(),
          signal: controller.signal,
          body: JSON.stringify({
            message: question,
            conversation_id: conversationId,
            opportunity_id: boundOpportunity || opportunityId,
            upload_ids: uploads.map((item) => item.id).filter(Boolean),
            ...deviceToday(),
          }),
        });
        if (response.status === 401) {
          setDraft(question);
          setMessages((current) => current.filter((item) => item.id !== mine.id && item.id !== reply.id));
          setError("sign-in");
          return;
        }
        if (response.status === 403) {
          setMessages((current) => current.filter((item) => item.id !== mine.id && item.id !== reply.id));
          setError("closed");
          return;
        }
        if (response.status === 429) {
          const detail = await response.text();
          setError(detail.includes("paused") ? "paused" : "quota");
          return;
        }
        if (response.status === 409) {
          setError("switch");
          return;
        }
        if (!response.ok || !response.body) {
          setError("error");
          return;
        }
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let halted = false;
        for (;;) {
          if (stopRef.current) {
            halted = true;
            break;
          }
          const step = await reader.read();
          if (step.done) break;
          buffer += decoder.decode(step.value, { stream: true });
          const chunks = buffer.split("\n\n");
          buffer = chunks.pop() || "";
          for (const chunk of chunks) {
            const line = chunk.split("\n").find((row) => row.startsWith("data: "));
            if (!line) continue;
            const data = line.slice(6);
            if (data === "[DONE]") continue;
            const event = JSON.parse(data) as {
              type: string;
              text?: string;
              key?: string;
              conversation_id?: string;
              citations?: Citation[];
              url?: string;
              label?: string;
              page?: number;
              heading?: string;
            };
            if (stopRef.current) {
              halted = true;
              break;
            }
            if (event.type === "delta" && event.text) {
              pushText(reply.id, event.text);
            } else if (event.type === "reset") {
              clearText(reply.id);
            } else if (event.type === "status") {
              setStatus(event.key ?? null);
            } else if (event.type === "citation") {
              const citation = {
                url: event.url,
                label: event.label,
                page: event.page,
                heading: event.heading,
              };
              setMessages((current) =>
                current.map((item) =>
                  item.id === reply.id ? { ...item, citations: [...(item.citations || []), citation] } : item,
                ),
              );
            } else if (event.type === "done" && event.conversation_id) {
              setConversationId(event.conversation_id);
            }
          }
          if (halted) break;
        }
        if (halted) await reader.cancel();
      } catch (err) {
        if (aborted(err)) {
          const shown = shownRef.current[reply.id] ?? "";
          targetRef.current[reply.id] = shown;
          if (!shown) {
            setMessages((current) => current.filter((item) => item.id !== reply.id));
          }
          setAnnounced(shown);
          return;
        }
        setError("error");
      } finally {
        busyRef.current = false;
        setBusy(false);
        abortRef.current = null;
        const target = targetRef.current[reply.id] ?? "";
        const shown = shownRef.current[reply.id] ?? "";
        if (shown === target) {
          setRevealing(false);
          if (target) setAnnounced(target);
        } else {
          scheduleReveal();
        }
      }
    },
    [boundOpportunity, busy, clearText, conversationId, opportunityId, pageTitle, pushText, scheduleReveal, uploads],
  );

  const stop = useCallback(() => {
    stopRef.current = true;
    if (timerRef.current != null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    const ids = Object.keys(targetRef.current);
    const id = ids[ids.length - 1];
    if (id) {
      const shown = shownRef.current[id] ?? "";
      targetRef.current[id] = shown;
      setMessages((current) => current.map((item) => (item.id === id ? { ...item, text: shown } : item)));
      setAnnounced(shown);
    }
    setRevealing(false);
    abortRef.current?.abort();
  }, []);

  const mismatch = Boolean(boundOpportunity && opportunityId && boundOpportunity !== opportunityId);

  useEffect(() => {
    if (!open) {
      switched.current = false;
      hold.current = false;
      return;
    }
    if (!mismatch || switched.current || hold.current) return;
    switched.current = true;
    setArchive({
      conversationId,
      opportunityId: boundOpportunity,
      title: boundTitle,
      messages,
    });
    setMessages([]);
    setConversationId(null);
    setBoundOpportunity(opportunityId);
    setBoundTitle(pageTitle);
    setUploads([]);
    setError(null);
  }, [open, mismatch, conversationId, boundOpportunity, boundTitle, messages, opportunityId, pageTitle]);

  const restore = useCallback(() => {
    setArchive((current) => {
      if (!current) return null;
      hold.current = true;
      setMessages(current.messages);
      setConversationId(current.conversationId);
      setBoundOpportunity(current.opportunityId);
      setBoundTitle(current.title);
      return null;
    });
  }, []);

  const addUpload = useCallback(
    async (file: File) => {
      const body = new FormData();
      body.append("file", file);
      if (conversationId) body.append("conversation_id", conversationId);
      const response = await fetch(`${API_URL}/assistant/uploads`, {
        method: "POST",
        headers: authHeaders(),
        body,
      });
      if (response.status === 401) {
        setError("sign-in");
        return;
      }
      if (!response.ok) {
        setError("error");
        return;
      }
      const saved = (await response.json()) as { id: string; name: string; pages: number };
      setUploads((current) => [
        ...current,
        { id: saved.id, name: saved.name, status: "ok", pages: saved.pages, removable: true },
      ]);
    },
    [conversationId],
  );

  const removeUpload = useCallback(async (id: string) => {
    await fetch(`${API_URL}/assistant/uploads/${id}`, { method: "DELETE", headers: headers() });
    setUploads((current) => current.filter((item) => item.id !== id));
  }, []);

  const subject = boundOpportunity ? boundTitle || pageTitle : opportunityId ? pageTitle : null;

  return {
    open,
    setOpen,
    messages,
    documents,
    uploads,
    busy,
    status,
    revealing,
    announced,
    stop,
    error,
    draft,
    setDraft,
    send,
    reset,
    addUpload,
    removeUpload,
    mismatch,
    subject,
    previousTitle: archive?.title || null,
    restore,
    refreshDocuments,
  };
}

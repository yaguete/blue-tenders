"use client";

import { useCallback, useEffect, useState } from "react";
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

export function useAssistantChat(opportunityId: string | null) {
  const [open, setOpen] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [boundOpportunity, setBoundOpportunity] = useState<string | null>(null);
  const [uploads, setUploads] = useState<DocChip[]>([]);
  const [documents, setDocuments] = useState<DocChip[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState("");

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
    setMessages([]);
    setConversationId(null);
    setBoundOpportunity(opportunityId);
    setUploads([]);
    setError(null);
  }, [opportunityId]);

  const send = useCallback(
    async (text: string) => {
      const question = text.trim();
      if (!question || busy) return;
      setError(null);
      setDraft("");
      const mine: ChatMessage = { id: crypto.randomUUID(), role: "user", text: question };
      const reply: ChatMessage = { id: crypto.randomUUID(), role: "assistant", text: "", citations: [] };
      setMessages((current) => [...current, mine, reply]);
      setBusy(true);
      if (!boundOpportunity) setBoundOpportunity(opportunityId);
      try {
        const response = await fetch(`${API_URL}/assistant`, {
          method: "POST",
          headers: headers(),
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
        for (;;) {
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
              conversation_id?: string;
              citations?: Citation[];
              url?: string;
              label?: string;
              page?: number;
              heading?: string;
            };
            if (event.type === "delta" && event.text) {
              const extra = event.text;
              setMessages((current) =>
                current.map((item) => (item.id === reply.id ? { ...item, text: item.text + extra } : item)),
              );
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
        }
      } catch {
        setError("error");
      } finally {
        setBusy(false);
      }
    },
    [boundOpportunity, busy, conversationId, opportunityId, uploads],
  );

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

  const mismatch = Boolean(boundOpportunity && opportunityId && boundOpportunity !== opportunityId);

  return {
    open,
    setOpen,
    messages,
    documents,
    uploads,
    busy,
    error,
    draft,
    setDraft,
    send,
    reset,
    addUpload,
    removeUpload,
    mismatch,
    refreshDocuments,
  };
}

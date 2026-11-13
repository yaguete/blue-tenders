"use client";

import { useState } from "react";
import { API_URL } from "@/lib/api";

export default function AlertsPage() {
  const [email, setEmail] = useState("");
  const [result, setResult] = useState<string | null>(null);
  return (
    <form
      className="max-w-md space-y-3 text-sm"
      onSubmit={async (event) => {
        event.preventDefault();
        const response = await fetch(`${API_URL}/alerts`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Demo-User": window.localStorage.getItem("demo-user") || "reader",
          },
          body: JSON.stringify({
            email,
            cadence: "weekly",
            filters: { status: ["open"] },
          }),
        });
        setResult(response.ok ? await response.text() : await response.text());
      }}
    >
      <h1 className="text-3xl font-semibold tracking-tight">Weekly alert</h1>
      <p className="text-muted-foreground">
        Creating this is the consent. The reply includes a one-click unsubscribe link.
      </p>
      <input
        type="email"
        required
        value={email}
        onChange={(event) => setEmail(event.target.value)}
        placeholder="you@organisation.org"
        className="w-full border border-border px-2 py-1"
      />
      <button type="submit" className="bg-primary px-3 py-2 text-primary-foreground">
        Save search
      </button>
      {result && <pre className="whitespace-pre-wrap font-mono text-xs">{result}</pre>}
    </form>
  );
}

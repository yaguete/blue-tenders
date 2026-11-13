"use client";

import { useState } from "react";
import { API_URL } from "@/lib/api";

export default function ReviewPage() {
  const [token, setToken] = useState("");
  const [rows, setRows] = useState<string | null>(null);
  return (
    <form
      className="max-w-md space-y-3 text-sm"
      onSubmit={async (event) => {
        event.preventDefault();
        const response = await fetch(`${API_URL}/admin/review`, { headers: { "X-Admin-Token": token } });
        setRows(await response.text());
      }}
    >
      <h1 className="text-3xl font-semibold tracking-tight">Review queue</h1>
      <input
        type="password"
        value={token}
        onChange={(event) => setToken(event.target.value)}
        className="w-full border border-border px-2 py-1"
        placeholder="Admin token"
      />
      <button type="submit" className="bg-primary px-3 py-2 text-primary-foreground">
        Load
      </button>
      {rows && <pre className="whitespace-pre-wrap font-mono text-xs">{rows}</pre>}
    </form>
  );
}

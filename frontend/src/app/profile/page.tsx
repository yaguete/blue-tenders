"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { t } from "@/lib/i18n";

export default function ProfilePage() {
  const [name, setName] = useState("reader");
  const [country, setCountry] = useState("ES");
  const [entity, setEntity] = useState("foundation");
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    const stored = window.localStorage.getItem("demo-user");
    if (stored) setName(stored);
  }, []);

  return (
    <form
      className="max-w-md space-y-3 text-sm"
      onSubmit={async (event) => {
        event.preventDefault();
        window.localStorage.setItem("demo-user", name);
        try {
          await api("/me/profile", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, country, entity_type: entity, subsectors: ["offshore-wind"] }),
          });
          setMessage("Saved on this browser.");
        } catch {
          setMessage(t("signIn"));
        }
      }}
    >
      <h1 className="text-3xl font-semibold tracking-tight">Organisation</h1>
      <label className="block">
        Name used for this demo
        <input value={name} onChange={(event) => setName(event.target.value)} className="mt-1 w-full border border-border px-2 py-1" />
      </label>
      <label className="block">
        Country
        <input value={country} onChange={(event) => setCountry(event.target.value)} className="mt-1 w-full border border-border px-2 py-1" />
      </label>
      <label className="block">
        Entity type
        <select value={entity} onChange={(event) => setEntity(event.target.value)} className="mt-1 w-full border border-border px-2 py-1">
          <option value="foundation">foundation</option>
          <option value="sme">sme</option>
          <option value="research">research</option>
          <option value="public_body">public body</option>
        </select>
      </label>
      <button type="submit" className="bg-primary px-3 py-2 text-primary-foreground">
        Save
      </button>
      {message && <p>{message}</p>}
      <p className="flex gap-4 pt-2">
        <Link className="underline" href="/saved">
          Saved
        </Link>
        <Link className="underline" href="/alerts">
          Alerts
        </Link>
      </p>
    </form>
  );
}

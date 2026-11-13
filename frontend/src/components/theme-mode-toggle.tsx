"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Monitor, Moon, Smartphone, Sun } from "lucide-react";
import { cn } from "@/lib/utils";
import { applyTheme, readTheme, setTheme, type ThemeMode } from "@/lib/theme";

const MODES = [
  { id: "system", label: "System" },
  { id: "light", label: "Light" },
  { id: "dark", label: "Dark" },
] as const satisfies ReadonlyArray<{ id: ThemeMode; label: string }>;

function Glyph({ id, className }: { id: ThemeMode; className?: string }) {
  if (id === "light") return <Sun className={className} aria-hidden />;
  if (id === "dark") return <Moon className={className} aria-hidden />;
  return (
    <>
      <Smartphone className={cn(className, "md:hidden")} aria-hidden />
      <Monitor className={cn(className, "hidden md:block")} aria-hidden />
    </>
  );
}

export function ThemeModeToggle({ className }: { className?: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [mode, setMode] = useState<ThemeMode | "">("");
  const [box, setBox] = useState({ x: 0, y: 0, w: 0, h: 0 });

  const measure = useCallback(() => {
    const root = containerRef.current;
    const active = root?.querySelector<HTMLElement>("[data-indicator-active='true']");
    if (!root || !active) return;
    const rootRect = root.getBoundingClientRect();
    const rect = active.getBoundingClientRect();
    const style = getComputedStyle(root);
    // El indicador es absolute: su origen es el borde interior, no el exterior.
    const borderLeft = parseFloat(style.borderLeftWidth) || 0;
    const borderTop = parseFloat(style.borderTopWidth) || 0;
    setBox({
      x: rect.left - rootRect.left - borderLeft,
      y: rect.top - rootRect.top - borderTop,
      w: rect.width,
      h: rect.height,
    });
  }, []);

  useLayoutEffect(() => {
    const stored = readTheme();
    setMode(stored);
    applyTheme(stored);
  }, []);

  useEffect(() => {
    function onChange() {
      setMode(readTheme());
    }
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    function onSystem() {
      if (readTheme() === "system") applyTheme("system");
    }
    window.addEventListener("blue-tender-theme", onChange);
    media.addEventListener("change", onSystem);
    return () => {
      window.removeEventListener("blue-tender-theme", onChange);
      media.removeEventListener("change", onSystem);
    };
  }, []);

  useLayoutEffect(() => {
    measure();
  }, [measure, mode]);

  useEffect(() => {
    const root = containerRef.current;
    if (!root) return;
    const observer = new ResizeObserver(() => measure());
    observer.observe(root);
    return () => observer.disconnect();
  }, [measure]);

  return (
    <div
      ref={containerRef}
      role="radiogroup"
      aria-label="Theme"
      className={cn("relative inline-flex shrink-0 items-center rounded-full border border-border p-0.5", className)}
    >
      {box.w > 0 && (
        <span
          aria-hidden
          className="pointer-events-none absolute top-0 left-0 z-0 rounded-full bg-foreground/10 transition-[transform,width,height] duration-200 ease-out motion-reduce:transition-none"
          style={{ transform: `translate(${box.x}px, ${box.y}px)`, width: box.w, height: box.h }}
        />
      )}
      {MODES.map(({ id, label }) => {
        const checked = mode === id;
        return (
          <button
            key={id}
            type="button"
            role="radio"
            aria-checked={checked}
            aria-label={label}
            data-indicator-active={checked ? "true" : undefined}
            onClick={() => {
              setTheme(id);
              setMode(id);
            }}
            className={cn(
              "relative z-10 flex size-8 cursor-pointer items-center justify-center rounded-full text-muted-foreground outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring",
              checked && "text-foreground",
            )}
          >
            <Glyph id={id} className="size-3.5" />
          </button>
        );
      })}
    </div>
  );
}

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Assistant } from "@/components/assistant/drawer";
import { ThemeModeToggle } from "@/components/theme-mode-toggle";
import { clearCompare } from "@/lib/compare";
import { setTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";

const links = [
  ["Search", "/search"],
  ["Funders", "/funders"],
  ["Profile", "/profile"],
];

const legal = [
  ["Privacy", "/legal/privacy"],
  ["Terms", "/legal/terms"],
  ["Cookies", "/legal/cookies"],
];

function MenuGlyph({ open }: { open: boolean }) {
  return (
    <svg viewBox="0 0 20 20" className="size-5" fill="none" aria-hidden>
      {open ? (
        <path d="M5.5 5.5l9 9M14.5 5.5l-9 9" stroke="currentColor" strokeWidth="1.5" />
      ) : (
        <path d="M3 7h8.5M3 13h14" stroke="currentColor" strokeWidth="1.5" />
      )}
    </svg>
  );
}

function BrandLink({ mark = true }: { mark?: boolean }) {
  return (
    <Link href="/" className="flex shrink-0 items-center gap-2 text-sm font-semibold tracking-tight whitespace-nowrap">
      {mark && (
        <>
          <img src="/brand/mark.svg" alt="" width={32} height={32} className="size-8 dark:hidden" />
          <img src="/brand/mark-on-dark.png" alt="" width={32} height={32} className="hidden size-8 dark:block" />
        </>
      )}
      Blue Tender
    </Link>
  );
}

function isCurrent(pathname: string, href: string) {
  if (href === "/search") {
    return pathname === "/search" || pathname.startsWith("/opportunities") || pathname.startsWith("/compare");
  }
  if (href === "/profile") {
    return pathname === "/profile" || pathname.startsWith("/saved") || pathname.startsWith("/alerts");
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

function NavLinks({ pathname, onNavigate, menu }: { pathname: string; onNavigate?: () => void; menu?: boolean }) {
  return (
    <>
      {links.map(([label, href]) => {
        const current = isCurrent(pathname, href);
        return (
          <Link
            key={href}
            href={href}
            aria-current={current ? "page" : undefined}
            className={cn(
              "hover:text-foreground",
              menu && "block border-l-2 py-2.5 pl-3 text-base",
              menu && (current ? "border-foreground" : "border-transparent"),
              !menu && (current ? "text-base" : "text-sm"),
              current ? "font-semibold text-foreground" : "text-muted-foreground",
            )}
            onClick={() => {
              if (href === "/search") clearCompare();
              onNavigate?.();
            }}
          >
            {label}
          </Link>
        );
      })}
    </>
  );
}

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    setMenuOpen(false);
  }, [pathname]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "/" && document.activeElement?.tagName !== "INPUT") {
        event.preventDefault();
        document.getElementById("q")?.focus();
      }
      if (event.key === "Escape") setMenuOpen(false);
      if (event.key === "d" && event.metaKey) return;
      if (event.key.toLowerCase() === "d" && event.altKey) {
        event.preventDefault();
        const dark = document.documentElement.classList.contains("dark");
        setTheme(dark ? "light" : "dark");
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="flex min-h-screen flex-col">
      {menuOpen && (
        <button
          type="button"
          aria-label="Close menu"
          className="fixed inset-0 z-20 bg-foreground/10 backdrop-blur sm:hidden dark:bg-black/40"
          onClick={() => setMenuOpen(false)}
        />
      )}
      <header className={cn("fixed inset-x-0 top-0 z-30", menuOpen && "bg-background sm:bg-transparent")}>
        <div
          aria-hidden
          className={cn(
            "pointer-events-none absolute inset-x-0 top-0 h-32 bg-background/55 backdrop-blur-xl backdrop-saturate-150 [-webkit-mask-image:linear-gradient(to_bottom,black_28%,transparent)] [mask-image:linear-gradient(to_bottom,black_28%,transparent)]",
            menuOpen && "max-sm:hidden",
          )}
        />
        <div className="relative mx-auto grid max-w-6xl grid-cols-[1fr_auto] items-center gap-3 px-4 py-3 sm:grid-cols-[1fr_auto_1fr]">
          <BrandLink />
          <nav className="hidden items-center justify-center gap-4 sm:flex" aria-label="Primary">
            <NavLinks pathname={pathname} />
          </nav>
          <div className="flex justify-end sm:hidden">
            <button
              type="button"
              className="flex size-9 cursor-pointer items-center justify-center text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
              aria-expanded={menuOpen}
              aria-controls="site-menu"
              aria-label={menuOpen ? "Close menu" : "Open menu"}
              onClick={() => setMenuOpen((open) => !open)}
            >
              <MenuGlyph open={menuOpen} />
            </button>
          </div>
        </div>
        {menuOpen && (
          <nav id="site-menu" aria-label="Primary" className="relative px-4 py-2 sm:hidden">
            <NavLinks pathname={pathname} menu onNavigate={() => setMenuOpen(false)} />
          </nav>
        )}
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 pt-28 pb-10">{children}</main>
      <footer className="px-4 pt-8 pb-28">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex w-full items-center justify-between gap-3 sm:w-auto">
            <div className="flex items-center gap-1">
              <BrandLink mark={false} />
              <p className="relative top-px text-xs whitespace-nowrap text-muted-foreground">© 2026</p>
            </div>
            <ThemeModeToggle className="shrink-0 sm:hidden" />
          </div>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-3 sm:gap-6">
            <nav className="flex flex-wrap gap-x-3 gap-y-2 text-sm text-muted-foreground">
              {legal.map(([label, href]) => (
                <Link key={href} href={href} className="hover:text-foreground">
                  {label}
                </Link>
              ))}
              <a href="mailto:yago@thinkmaketest.ai" className="hover:text-foreground">
                Contact
              </a>
            </nav>
            <ThemeModeToggle className="hidden shrink-0 sm:inline-flex" />
          </div>
        </div>
      </footer>
      <Suspense fallback={null}>
        <Assistant />
      </Suspense>
    </div>
  );
}

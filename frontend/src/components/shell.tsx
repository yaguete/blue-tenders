"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense, useEffect } from "react";
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

function BrandLink() {
  return (
    <Link href="/" className="flex shrink-0 items-center gap-2 text-sm font-semibold tracking-tight whitespace-nowrap">
      <img src="/brand/mark.svg" alt="" width={32} height={32} className="size-8 dark:hidden" />
      <img src="/brand/mark-on-dark.png" alt="" width={32} height={32} className="hidden size-8 dark:block" />
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

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "/" && document.activeElement?.tagName !== "INPUT") {
        event.preventDefault();
        document.getElementById("q")?.focus();
      }
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
      <header className="fixed inset-x-0 top-0 z-30">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 h-32 bg-background/55 backdrop-blur-xl backdrop-saturate-150 [-webkit-mask-image:linear-gradient(to_bottom,black_28%,transparent)] [mask-image:linear-gradient(to_bottom,black_28%,transparent)]"
        />
        <div className="relative mx-auto grid max-w-6xl grid-cols-[1fr_auto_1fr] items-center gap-3 px-4 py-3">
          <BrandLink />
          <nav className="flex items-center gap-3 sm:gap-4">
            {links.map(([label, href]) => {
              const current = isCurrent(pathname, href);
              return (
                <Link
                  key={href}
                  href={href}
                  aria-current={current ? "page" : undefined}
                  className={cn(
                    "hover:text-foreground",
                    current ? "text-base font-semibold text-foreground" : "text-sm text-muted-foreground",
                  )}
                  onClick={href === "/search" ? () => clearCompare() : undefined}
                >
                  {label}
                </Link>
              );
            })}
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 pt-28 pb-10">{children}</main>
      <footer className="px-4 pt-8 pb-24">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4">
          <div className="flex items-center gap-1">
            <BrandLink />
            <p className="relative top-px text-xs whitespace-nowrap text-muted-foreground">© 2026</p>
          </div>
          <div className="flex items-center gap-6">
            <nav className="flex gap-3 text-sm whitespace-nowrap text-muted-foreground">
              {legal.map(([label, href]) => (
                <Link key={href} href={href} className="hover:text-foreground">
                  {label}
                </Link>
              ))}
              <a href="mailto:yago@thinkmaketest.ai" className="hover:text-foreground">
                Contact
              </a>
            </nav>
            <ThemeModeToggle className="shrink-0" />
          </div>
        </div>
      </footer>
      <Suspense fallback={null}>
        <Assistant />
      </Suspense>
    </div>
  );
}

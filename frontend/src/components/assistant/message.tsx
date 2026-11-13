"use client";

import type { ReactNode } from "react";
import { Mail, SquareArrowOutUpRight } from "lucide-react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatMessage, Citation } from "@/lib/assistant-chat";

const URL_PATTERN = /(?<!\]\()(?<!\()https?:\/\/[^\s<>)\]]+/g;
const EMAIL_PATTERN = /(?<!\]\()(?<!mailto:)\b([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})\b/gi;

const PROTECTED = /(```[\s\S]*?```|\[[^\]]*\]\([^)]*\))/g;

const MARKDOWN = [
  "max-w-full",
  "[&_h1]:mt-3 [&_h1]:font-semibold [&_h2]:mt-3 [&_h2]:font-semibold",
  "[&_h3]:mt-3 [&_h3]:font-semibold [&_h4]:mt-3 [&_h4]:font-semibold",
  "[&_h1:first-child]:mt-0 [&_h2:first-child]:mt-0 [&_h3:first-child]:mt-0",
  "[&_ul]:my-2 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:my-2 [&_ol]:list-decimal [&_ol]:pl-5",
  "[&_li]:my-0.5",
  "[&_th]:border [&_th]:border-border [&_th]:bg-muted [&_th]:px-2 [&_th]:py-1 [&_th]:font-medium",
  "[&_td]:border [&_td]:border-border [&_td]:px-2 [&_td]:py-1 [&_td]:align-top",
  "[&_pre]:my-2 [&_pre]:overflow-x-auto [&_pre]:bg-muted [&_pre]:p-2",
  "[&_code]:font-mono [&_code]:text-xs [&_p]:my-2",
].join(" ");

function outside(text: string, edit: (part: string) => string): string {
  return text
    .split(PROTECTED)
    .map((part, index) => (index % 2 === 1 ? part : edit(part)))
    .join("");
}

function normalizeMarkdown(text: string): string {
  return outside(text.replace(/\r\n/g, "\n"), (part) =>
    part
      .replace(/([^\n])[ \t]+(#{1,6})(?=[ \t])/g, "$1\n\n$2")
      .replace(/([.!?])[ \t]+([-*]|\d{1,2}\.)[ \t]+(?=\S)/g, "$1\n$2 ")
      .replace(/([^\n])[ \t]+([-*])[ \t]+(?=\*\*)/g, "$1\n$2 "),
  );
}

function linkPages(text: string, url?: string): string {
  if (!url) return text;
  const base = url.split("#")[0];
  const pdf = base.toLowerCase().includes(".pdf");
  const pages =
    /\b((?:p[aá]ginas?|paginas?|p[aá]gs?|pags?|pages?|pp)\.?|p\.)\s+(\d+)(?:\s*[-–—]\s*\d+)?/gi;
  return outside(text, (part) =>
    part.replace(pages, (mention, _label, start: string) => {
      const target = pdf ? `${base}#page=${start}` : base;
      return `[${mention}](${target})`;
    }),
  );
}

function pageTarget(text: string, citations: Citation[]): string | undefined {
  const cited = citations.find((item) => item.url)?.url;
  if (cited) return cited;
  return text.match(/https?:\/\/[^\s<>)\]]+/)?.[0].replace(/[.,;:]+$/, "");
}

function prepare(text: string, citations: Citation[]): string {
  const normalized = normalizeMarkdown(text);
  return linkify(linkPages(normalized, pageTarget(text, citations)));
}

function linkify(text: string): string {
  return outside(text, (part) => {
    const withMail = part.replace(EMAIL_PATTERN, (email) => `[${email}](mailto:${email})`);
    return withMail.replace(URL_PATTERN, (raw) => {
      const url = raw.replace(/[.,;:]+$/, "");
      return `[${url}](${url})${raw.slice(url.length)}`;
    });
  });
}

function collapse(value: string, max = 36): string {
  if (value.length <= max) return value;
  return `${value.slice(0, max).replace(/[/?&=]+$/, "")}…`;
}

function textOf(children: ReactNode): string {
  if (typeof children === "string" || typeof children === "number") return String(children);
  if (Array.isArray(children)) return children.map(textOf).join("");
  return "";
}

function SmartLink({ href, children }: { href?: string; children?: ReactNode }) {
  if (!href) return <>{children}</>;
  const mail = href.startsWith("mailto:");
  const address = mail ? href.slice("mailto:".length) : href;
  const written = textOf(children);
  const label = written === address || written === href ? collapse(address) : written;
  const Icon = mail ? Mail : SquareArrowOutUpRight;
  return (
    <a
      href={href}
      target={mail ? undefined : "_blank"}
      rel={mail ? undefined : "noreferrer"}
      className="inline-flex max-w-full items-baseline gap-0.5 underline"
      title={address}
    >
      <span className="truncate">{label}</span>
      <Icon className="h-3 w-3 shrink-0 translate-y-px" aria-hidden />
    </a>
  );
}

function href(citation: Citation): string | undefined {
  if (!citation.url) return undefined;
  const base = citation.url.split("#")[0];
  if (citation.page && base.toLowerCase().includes(".pdf")) return `${base}#page=${citation.page}`;
  if (citation.heading) {
    const slug = citation.heading.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    return `${base}#${slug}`;
  }
  return citation.url;
}

export function Message({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <p className="max-w-[85%] bg-secondary px-3 py-2 text-sm leading-6">{message.text}</p>
      </div>
    );
  }
  if (!message.text && !(message.citations || []).length) return null;
  return (
    <div className="max-w-[95%] text-sm leading-6">
      {message.text && (
        <div className={MARKDOWN}>
          <Markdown
            remarkPlugins={[remarkGfm]}
            components={{
              a: SmartLink,
              table: ({ children }) => (
                <div className="my-2 overflow-x-auto">
                  <table className="w-full border-collapse text-left text-xs">{children}</table>
                </div>
              ),
            }}
          >
            {prepare(message.text, message.citations || [])}
          </Markdown>
        </div>
      )}
      {(message.citations || []).length > 0 && (
        <p className="mt-1 font-mono text-xs text-muted-foreground">
          {(message.citations || []).map((citation, index) => {
            const target = href(citation);
            const mark = citation.page ? `${index + 1} p.${citation.page}` : String(index + 1);
            return target ? (
              <a key={`${target}-${index}`} href={target} className="mr-2 underline">
                [{mark}]
              </a>
            ) : (
              <span key={index} className="mr-2">
                [{mark}]
              </span>
            );
          })}
        </p>
      )}
    </div>
  );
}

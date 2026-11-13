"use client";

import { ArrowLeft, Calendar, ChevronDown, Columns2, FileText, Globe, SquareArrowOutUpRight } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { LoadingState } from "@/components/loading-state";
import { api } from "@/lib/api";
import { addCompare, comparePath, useCompareIds } from "@/lib/compare";
import { calendarDay, money, shortTitle, shownBudget, when } from "@/lib/format";
import { t } from "@/lib/i18n";

type Block = {
  heading: string;
  text: string;
  origin: "extracted" | "generated";
  citations: { quote?: string | null; document_url?: string | null }[];
};

type Project = {
  id: string;
  acronym: string | null;
  title: string | null;
  role: string | null;
  url: string | null;
  programme_id: string | null;
  end_year: number | null;
  end_date?: string | null;
  evidence: string | null;
  buyer: string | null;
  amount_eur: number | null;
  base_amount_eur?: number | null;
  contract_end?: string | null;
};

type EndingPartner = {
  org_name: string;
  country: string | null;
  activity_type: string | null;
  pic: string | null;
  sme?: boolean | null;
  role: string | null;
  relevant?: boolean;
};

type Consortium = {
  id: string;
  acronym: string | null;
  title: string | null;
  url: string | null;
  programme_id: string | null;
  end_date: string;
  partners: EndingPartner[];
};

type EndingSoon = {
  status: "ok" | "no_match" | "not_loaded";
  window_months: number;
  total: number;
  consortia_total?: number;
  relevant_total?: number | null;
  consortia?: Consortium[];
};

type Partner = {
  org_name: string;
  country: string | null;
  activity_type: string | null;
  pic: string | null;
  sme?: boolean | null;
  score: number;
  demo?: boolean;
  projects: Project[];
};

type TrackRecord = {
  status: "ok" | "no_match" | "not_loaded" | "not_comparable";
  source: "cordis" | "ted_awards";
  total: number;
  loaded_at: string | null;
  since: string | null;
  items: Partner[];
};

type Detail = {
  id: string;
  source_id: string;
  title: string;
  title_en: string | null;
  url: string;
  kind: string;
  notice?: string | null;
  programme_id: string | null;
  funder_id: string | null;
  deadline_at: string | null;
  published_at?: string | null;
  budget_total_eur: number | null;
  budget: { amount: number | null; currency: string | null; amount_eur: number | null } | null;
  amount_min_eur: number | null;
  amount_max_eur: number | null;
  topic_id: string | null;
  call_id: string | null;
  type_of_action: string | null;
  status: string | null;
  cofunding_min: number | null;
  cofunding_max: number | null;
  consortium_required: boolean | null;
  eligible_entity_types: string[];
  language: string | null;
  summary_en: string | null;
  description: string | null;
  buyer: { name: string | null; country?: string | null } | null;
  updated_at: string | null;
  analysis: { summary: string | null; blocks: Block[]; model: string | null } | null;
  facts: {
    field: string;
    value?: string | number | null;
    origin: string;
    confidence: number;
    quote: string | null;
    document_url?: string | null;
  }[];
  documents: { url: string; name: string | null; kind?: string | null; access?: string | null }[];
  awards: { id: string; title: string; winner: string | null; amount_eur: number | null; url: string }[];
  track_record?: TrackRecord;
  ending_soon?: EndingSoon;
  partners: Partner[];
};

export default function OpportunityPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const compareIds = useCompareIds();
  const [item, setItem] = useState<Detail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [original, setOriginal] = useState(false);
  const [compareNote, setCompareNote] = useState<string | null>(null);
  const [trackOpen, setTrackOpen] = useState(false);
  const [endingOpen, setEndingOpen] = useState(false);

  useEffect(() => {
    setTrackOpen(false);
    setEndingOpen(false);
    api<Detail>(`/opportunities/${params.id}`)
      .then((body) => {
        setItem(body);
        setEndingOpen(body.ending_soon?.status === "ok");
      })
      .catch((err: Error) => setError(err.message));
  }, [params.id]);

  if (error) return <p className="text-sm text-status-urgent">{t("error")}</p>;
  if (!item) return <LoadingState label={t("loadingCall")} />;

  const low = item.facts.some((fact) => fact.confidence < 0.75 && ["deadline_at", "cofunding_min"].includes(fact.field));
  const category = [item.kind, item.funder_id, item.programme_id].filter(Boolean).join(" · ");
  const closed = item.status === "closed";
  const topic = Boolean(item.topic_id);
  const budgetValue =
    topic && item.budget_total_eur != null
      ? t("budgetForTopic").replace("{amount}", money(item.budget_total_eur))
      : shownBudget(item.budget_total_eur, item.budget?.amount, item.budget?.currency);
  const starred = topic && item.budget_total_eur != null;
  const files = item.documents.filter((doc) => isFile(doc, item.url));
  const deadlineValue =
    closed && item.deadline_at
      ? `${t("closedLabel")} · ${day(item.deadline_at)}`
      : closed
        ? t("closedLabel")
        : when(item.deadline_at);
  const callLine = callHeading(item);
  const englishHeading = shortTitle(item.title, item.title_en);
  const heading = original ? item.title : englishHeading;
  const hasTranslation = englishHeading.trim() !== item.title.trim();
  const notice = (item.summary_en || item.description || "").trim();
  const topicCount = factNumber(item, "call_topics_count");
  const portalNote = topic
    ? (topicCount != null ? t("portalListsTopics") : t("portalListsTopicsUnknown")).replace(
        "{count}",
        String(topicCount ?? ""),
      )
    : null;

  function goBack() {
    if (window.history.length > 1) {
      router.back();
      return;
    }
    router.push("/search");
  }

  function openCompare(id: string) {
    if (!compareIds.includes(id) && compareIds.length >= 4) {
      setCompareNote(t("compareFull"));
      return;
    }
    const next = addCompare(id);
    if (next.length < 2) {
      router.push("/search");
      return;
    }
    router.push(comparePath(next));
  }

  return (
    <article className="space-y-8">
      <header className="space-y-3">
        <button
          type="button"
          onClick={goBack}
          className="inline-flex cursor-pointer items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" aria-hidden />
          {t("back")}
        </button>
        <h1 className="text-3xl font-semibold tracking-tight">{heading}</h1>
        {item.buyer?.name && <p className="text-sm text-muted-foreground">{item.buyer.name}</p>}
        {topic && (
          <div className="space-y-1 text-sm">
            <p>
              {t("topicLabel")} {item.topic_id}
              {item.type_of_action ? ` · ${item.type_of_action}` : ""}
            </p>
            {callLine && <p>{callLine}</p>}
          </div>
        )}
        <dl className="my-6 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
          <Cell label="Deadline" value={deadlineValue} />
          <Cell label="Budget" value={starred ? `${budgetValue}*` : budgetValue} hint={grantLine(item)} />
          <Cell
            label="Co-funding"
            value={
              item.cofunding_min == null && item.cofunding_max == null
                ? "—"
                : `${item.cofunding_min ?? "?"}–${item.cofunding_max ?? "?"}%`
            }
          />
          <Cell
            label="Consortium"
            value={item.consortium_required == null ? "Not specified" : item.consortium_required ? "Required" : "Not required"}
          />
        </dl>
        {item.notice === "pin" && item.published_at && (
          <p className="text-sm text-muted-foreground">
            {t("seenOn").replace("{date}", calendarDay(item.published_at))}
          </p>
        )}
        <ScrapedFrom item={item} />
        {closed && topic && (
          <div className="space-y-1 text-sm text-muted-foreground">
            <p>{t("closedReference")}</p>
            {proposalLine(item) && <p>{proposalLine(item)}</p>}
          </div>
        )}
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <a
            href={item.url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex bg-primary px-3 py-1.5 text-sm text-primary-foreground"
          >
            {item.notice === "pin" ? t("officialPage") : topic ? t("openOnPortal") : t("officialCall")}
          </a>
          {!closed && item.deadline_at && (
            <a
              className="inline-flex items-center gap-1.5 text-sm underline"
              href={`${process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"}/opportunities/${item.id}/calendar`}
              target="_blank"
              rel="noreferrer"
            >
              <Calendar className="size-4 shrink-0" aria-hidden />
              Add deadline to calendar
            </a>
          )}
          <button
            type="button"
            className="inline-flex cursor-pointer items-center gap-1.5 text-sm underline"
            onClick={() => openCompare(item.id)}
          >
            <Columns2 className="size-4 shrink-0" aria-hidden />
            {t("compare")}
          </button>
          {files.length > 0 && (
            <ul className="flex flex-wrap items-center gap-x-4 gap-y-2">
              {files.map((doc) => (
                <li key={`${doc.url}-${doc.name}`}>
                  <a
                    href={doc.url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1.5 text-sm underline"
                  >
                    <FileText className="size-4 shrink-0" aria-hidden />
                    {doc.name || "Document"}
                  </a>
                </li>
              ))}
            </ul>
          )}
          {item.language && item.language !== "en" && hasTranslation && (
            <p className="inline-flex items-center gap-1.5 text-sm text-muted-foreground">
              <Globe className="size-4 shrink-0" aria-hidden />
              {original ? (
                <button type="button" className="cursor-pointer underline text-foreground" onClick={() => setOriginal(false)}>
                  {t("showEnglish")}
                </button>
              ) : (
                <>
                  <span>{t("translatedFrom").replace("{language}", languageName(item.language))}</span>
                  <button type="button" className="cursor-pointer underline text-foreground" onClick={() => setOriginal(true)}>
                    {t("viewOriginal")}
                  </button>
                </>
              )}
            </p>
          )}
        </div>
        {compareNote && <p className="text-sm text-muted-foreground">{compareNote}</p>}
        {low && <p className="text-sm text-status-soon">{t("verify")}</p>}
        <p className="flex flex-wrap items-baseline gap-x-4 font-mono text-xs text-muted-foreground/70">
          <span>{category}</span>
          <span>
            {t("updated")} {item.updated_at ? when(item.updated_at) : "—"}
          </span>
        </p>
        {portalNote && <p className="text-xs text-muted-foreground">* {portalNote}</p>}
      </header>

      <OverviewSection analysis={item.analysis} fallback={notice} />

      {item.awards.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold">Who won</h2>
          <ul className="mt-3 space-y-2 text-sm">
            {item.awards.map((award) => (
              <li key={award.id}>
                <a className="underline" href={award.url}>
                  {award.title}
                </a>
                {award.winner ? ` · ${award.winner}` : ""}
                {award.amount_eur != null ? ` · EUR ${award.amount_eur.toLocaleString("en-GB")}` : ""}
              </li>
            ))}
          </ul>
        </section>
      )}

      <TrackRecordSection item={item} open={trackOpen} onToggle={() => setTrackOpen((value) => !value)} />

      {item.kind === "grant" && item.ending_soon && (
        <EndingSoonSection item={item} open={endingOpen} onToggle={() => setEndingOpen((value) => !value)} />
      )}

      <footer className="space-y-1 font-mono text-xs text-muted-foreground">
        <p>
          <a className="underline" href={item.url}>
            {sourceLabel(item.source_id)}
          </a>
        </p>
        {item.track_record && (item.track_record.status === "ok" || item.track_record.status === "no_match") && (
          <p>{attribution(item.track_record)}</p>
        )}
      </footer>
    </article>
  );
}

function TrackRecordSection({ item, open, onToggle }: { item: Detail; open: boolean; onToggle: () => void }) {
  const partners = item.track_record?.items ?? item.partners;
  const count = item.track_record?.total ?? partners.length;
  const title = (count === 1 ? t("trackRecordTitleOne") : t("trackRecordTitle")).replace("{count}", String(count));
  const message = trackMessage(item);
  return (
    <section>
      <h2 className="text-lg font-semibold">
        <button
          type="button"
          aria-expanded={open}
          onClick={onToggle}
          className="inline-flex cursor-pointer items-center gap-2 text-left"
        >
          <span>{title}</span>
          <ChevronDown
            className={`size-4 shrink-0 text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`}
            aria-hidden
          />
        </button>
      </h2>
      {open && (
        <>
          {message && <p className="mt-3 text-sm text-muted-foreground">{message}</p>}
          <ul className="mt-3 space-y-3 text-sm">
            {partners.map((partner) => (
              <li key={partner.pic || partner.org_name}>
                <span className="font-medium">{partner.org_name}</span>
                {partner.country ? ` · ${partner.country}` : ""}
                {partner.activity_type ? ` · ${activityLabel(partner.activity_type)}` : ""}
                {partner.sme ? ` · ${t("trackRecordSme")}` : ""}
                {partner.demo ? " · sample" : ""}
                <ul className="mt-1 text-muted-foreground">
                  {partner.projects.map((project) => (
                    <li key={project.id || project.url || project.acronym}>
                      {project.url ? (
                        <a href={project.url} className="underline" target="_blank" rel="noreferrer">
                          {project.acronym || project.title}
                        </a>
                      ) : (
                        project.acronym || project.title
                      )}
                      {project.role ? ` · ${project.role}` : ""}
                      {project.programme_id ? ` · ${programmeLabel(project.programme_id)}` : ""}
                      {project.end_year ? <span className="tabular"> · {project.end_year}</span> : ""}
                      {project.buyer ? ` · ${project.buyer}` : ""}
                      {project.amount_eur != null ? (
                        <span className="tabular">
                          {" · "}EUR {project.amount_eur.toLocaleString("en-GB")}
                          {project.base_amount_eur != null
                            ? ` (${t("baseBudget").replace("{amount}", project.base_amount_eur.toLocaleString("en-GB"))})`
                            : ""}
                        </span>
                      ) : null}
                      {project.contract_end ? ` · ${t("ends").replace("{date}", dateOnly(project.contract_end))}` : ""}
                      {evidenceLabel(project.evidence) ? ` · ${evidenceLabel(project.evidence)}` : ""}
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
          {item.track_record && item.track_record.total > (item.track_record.items?.length ?? 0) && (
            <p className="mt-3 font-mono text-xs text-muted-foreground">
              {t("trackRecordShowing")
                .replace("{shown}", String(item.track_record.items.length))
                .replace("{total}", String(item.track_record.total))}
            </p>
          )}
        </>
      )}
    </section>
  );
}

function EndingSoonSection({ item, open, onToggle }: { item: Detail; open: boolean; onToggle: () => void }) {
  const record = item.ending_soon;
  const [month, setMonth] = useState<string | null>(null);
  const [relevantOnly, setRelevantOnly] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  if (!record) return null;
  const consortia = record.consortia ?? [];
  const consortiaTotal = record.consortia_total ?? consortia.length;
  const months = String(record.window_months);
  const title = (consortiaTotal === 1 ? t("endingSoonConsortiaOne") : t("endingSoonConsortia"))
    .replace("{count}", String(consortiaTotal))
    .replace("{months}", months);
  const orgs = (record.total === 1 ? t("endingSoonOrgsOne") : t("endingSoonOrgs")).replace(
    "{count}",
    String(record.total),
  );
  const relevant =
    record.relevant_total == null
      ? null
      : t("endingSoonRelevantCount").replace("{count}", String(record.relevant_total));
  const message =
    record.status === "not_loaded"
      ? t("endingSoonNotLoaded")
      : record.status === "no_match"
        ? t("endingSoonNoMatch").replace("{months}", months)
        : null;
  const listed = relevantOnly ? consortia.filter((consortium) => consortium.partners.some((partner) => partner.relevant)) : consortia;
  const columns = monthColumns(record.window_months);
  const peak = Math.max(1, ...columns.map((column) => listed.filter((consortium) => consortium.end_date.startsWith(column.key)).length));
  const shown = month ? listed.filter((consortium) => consortium.end_date.startsWith(month)) : listed;
  const visible = month || showAll ? shown : shown.slice(0, 10);
  return (
    <section>
      <h2 className="text-lg font-semibold">
        <button
          type="button"
          aria-expanded={open}
          onClick={onToggle}
          className="inline-flex cursor-pointer items-center gap-2 text-left"
        >
          <span>{title}</span>
          <ChevronDown
            className={`size-4 shrink-0 text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`}
            aria-hidden
          />
        </button>
      </h2>
      {open && (
        <>
          <p className="mt-2 font-mono text-xs text-muted-foreground">
            {orgs}
            {relevant ? ` · ${relevant}` : ""}
          </p>
          {message && <p className="mt-3 text-sm text-muted-foreground">{message}</p>}
          {record.status === "ok" && (
            <>
              <div className="mt-4 flex flex-wrap items-end justify-between gap-3">
                <div className="flex min-w-0 flex-1 items-end gap-1" role="group" aria-label={t("endingSoonMonths")}>
                  {columns.map((column) => {
                    const count = listed.filter((consortium) => consortium.end_date.startsWith(column.key)).length;
                    const pressed = month === column.key;
                    const height = count === 0 ? 4 : Math.max(8, Math.round((count / peak) * 64));
                    const label = (count === 1 ? t("endingSoonMonthOne") : t("endingSoonMonth"))
                      .replace("{month}", column.full)
                      .replace("{count}", String(count));
                    return (
                      <button
                        key={column.key}
                        type="button"
                        aria-pressed={pressed}
                        aria-label={label}
                        onClick={() => setMonth(pressed ? null : column.key)}
                        className="flex min-w-0 flex-1 cursor-pointer flex-col items-center gap-1"
                      >
                        <span className="tabular font-mono text-xs">{count}</span>
                        <span
                          className={`w-full ${pressed ? "bg-accent-ink" : "bg-muted-foreground/40"}`}
                          style={{ height }}
                        />
                        <span className="font-mono text-[10px] leading-tight text-muted-foreground">{column.short}</span>
                      </button>
                    );
                  })}
                </div>
                {record.relevant_total != null && record.relevant_total > 0 && (
                  <button
                    type="button"
                    aria-pressed={relevantOnly}
                    onClick={() => {
                      setRelevantOnly((value) => !value);
                      setMonth(null);
                    }}
                    className={`cursor-pointer border border-border px-2 py-1 text-sm ${relevantOnly ? "bg-accent-wash" : "bg-card"}`}
                  >
                    {t("endingSoonOnlyRelevant")}
                  </button>
                )}
              </div>
              <ul className="mt-4 space-y-3">
                {visible.map((consortium) => (
                  <ConsortiumCard
                    key={consortium.id}
                    consortium={consortium}
                    expanded={Boolean(expanded[consortium.id])}
                    onToggle={() => setExpanded((current) => ({ ...current, [consortium.id]: !current[consortium.id] }))}
                  />
                ))}
              </ul>
              {!month && !showAll && shown.length > 10 && (
                <button
                  type="button"
                  onClick={() => setShowAll(true)}
                  className="mt-3 cursor-pointer text-sm underline"
                >
                  {t("endingSoonShowAll").replace("{count}", String(shown.length))}
                </button>
              )}
            </>
          )}
          <p className="mt-3 font-mono text-xs text-muted-foreground">{t("endingSoonFoot")}</p>
        </>
      )}
    </section>
  );
}

function ConsortiumCard({
  consortium,
  expanded,
  onToggle,
}: {
  consortium: Consortium;
  expanded: boolean;
  onToggle: () => void;
}) {
  const partners = [...consortium.partners].sort((left, right) => {
    const rank = (partner: EndingPartner) => (partner.role === "coordinator" ? 0 : partner.relevant ? 1 : 2);
    return rank(left) - rank(right) || (left.org_name || "").localeCompare(right.org_name || "");
  });
  const shown = expanded ? partners : partners.slice(0, 6);
  const count = partners.length;
  const name = consortium.acronym || consortium.title;
  return (
    <li className="border border-border bg-card px-4 py-3 text-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        {consortium.url ? (
          <a href={consortium.url} className="font-medium underline" target="_blank" rel="noreferrer">
            {name}
          </a>
        ) : (
          <span className="font-medium">{name}</span>
        )}
        <span className="tabular font-mono text-xs text-muted-foreground">
          {t("ends").replace("{date}", dateOnly(consortium.end_date))}
        </span>
      </div>
      {consortium.acronym && consortium.title && (
        <p className="mt-1 truncate text-muted-foreground">{consortium.title}</p>
      )}
      <p className="mt-1 font-mono text-xs text-muted-foreground">
        {[
          consortium.programme_id ? programmeLabel(consortium.programme_id) : null,
          (count === 1 ? t("endingSoonPartnersOne") : t("endingSoonPartners")).replace("{count}", String(count)),
        ]
          .filter(Boolean)
          .join(" · ")}
      </p>
      <ul className="mt-2 space-y-1 text-muted-foreground">
        {shown.map((partner) => (
          <li key={partner.pic || partner.org_name}>
            <span className="text-foreground">{partner.org_name}</span>
            {partner.country ? ` · ${partner.country}` : ""}
            {partner.activity_type ? ` · ${activityLabel(partner.activity_type)}` : ""}
            {partner.sme ? ` · ${t("trackRecordSme")}` : ""}
            {roleLabel(partner.role) ? ` · ${roleLabel(partner.role)}` : ""}
            {partner.relevant ? ` · ${t("endingSoonRelevant")}` : ""}
          </li>
        ))}
      </ul>
      {count > 6 && (
        <button type="button" onClick={onToggle} className="mt-2 cursor-pointer text-xs underline">
          {expanded ? t("endingSoonShowFewer") : t("endingSoonMore").replace("{count}", String(count - 6))}
        </button>
      )}
    </li>
  );
}

function monthColumns(windowMonths: number): { key: string; short: string; full: string }[] {
  const now = new Date();
  const columns = [];
  for (let offset = 0; offset <= windowMonths; offset += 1) {
    const day = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + offset, 1));
    const key = `${day.getUTCFullYear()}-${String(day.getUTCMonth() + 1).padStart(2, "0")}`;
    const shortMonth = new Intl.DateTimeFormat("en", { month: "short", timeZone: "UTC" }).format(day);
    const showYear = offset === 0 || day.getUTCMonth() === 0;
    columns.push({
      key,
      short: showYear ? `${shortMonth} ${day.getUTCFullYear()}` : shortMonth,
      full: new Intl.DateTimeFormat("en", { month: "long", year: "numeric", timeZone: "UTC" }).format(day),
    });
  }
  return columns;
}

function roleLabel(role: string | null): string | null {
  if (!role || role === "participant") return null;
  const key = `role${role}`;
  const label = t(key);
  return label === key ? role : label;
}

function OverviewSection({ analysis, fallback }: { analysis: Detail["analysis"]; fallback?: string }) {
  const blocks = analysis?.blocks ?? [];
  const summaryBlock = blocks.find((block) => block.heading.trim().toLowerCase() === "summary");
  const summary = analysis?.summary;
  const lead =
    summaryBlock?.text ||
    (summary && !blocks.some((block) => block.text === summary) ? summary : null) ||
    (blocks.length === 0 ? fallback : null);
  const leadSource = summaryBlock ? sourceHref(summaryBlock) : null;
  const rows = blocks.filter((block) => block !== summaryBlock);
  if (!lead && rows.length === 0) return null;
  return (
    <section>
      <h2 className="text-lg font-semibold">{t("callOverview")}</h2>
      {lead && (
        <p className="mt-3 text-base leading-7">
          {lead}
          {leadSource && <SourceLink href={leadSource} />}
        </p>
      )}
      {rows.length > 0 && (
        <dl className="mt-6 divide-y divide-border border-y border-border">
          {rows.map((block) => {
            const source = sourceHref(block);
            return (
              <div key={block.heading} className="grid gap-x-10 gap-y-1.5 py-5 md:grid-cols-[13rem_1fr]">
                <dt className="text-sm font-medium text-accent-ink">{block.heading}</dt>
                <dd className="text-sm leading-6 text-foreground/85">
                  {block.text}
                  {source && <SourceLink href={source} />}
                </dd>
              </div>
            );
          })}
        </dl>
      )}
    </section>
  );
}

function SourceLink({ href }: { href: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="ml-2 inline-flex items-baseline gap-1 whitespace-nowrap text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
    >
      {t("source")}
      <SquareArrowOutUpRight className="size-3 self-center" aria-hidden />
    </a>
  );
}

function isFile(doc: Detail["documents"][number], pageUrl: string): boolean {
  // The topic text is already on this page and portal links open the same official page.
  if (doc.kind === "topic_text") return false;
  if (doc.access === "link_only" && doc.kind !== "portal") return false;
  return doc.url.split("#")[0] !== pageUrl.split("#")[0];
}

const languageNames = new Intl.DisplayNames(["en"], { type: "language" });

function languageName(code: string): string {
  try {
    const name = languageNames.of(code);
    if (!name) return code;
    return name.charAt(0).toUpperCase() + name.slice(1);
  } catch {
    return code;
  }
}

function sourceHref(block: Block): string | null {
  for (const citation of block.citations) {
    if (citation.quote?.startsWith("http")) return citation.quote;
  }
  for (const citation of block.citations) {
    if (citation.document_url?.startsWith("http")) return citation.document_url;
  }
  return null;
}

function Cell({ label, value, hint }: { label: string; value: string; hint?: string | null }) {
  return (
    <div className="border border-border bg-card px-4 py-3">
      <dt className="font-mono text-xs text-muted-foreground">{label}</dt>
      <dd className="tabular mt-1.5 text-base font-medium">{value}</dd>
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

function factNumber(item: Detail, field: string): number | null {
  const fact = item.facts.find((row) => row.field === field);
  if (fact == null || fact.value == null || fact.value === "") return null;
  const number = Number(fact.value);
  return Number.isFinite(number) ? number : null;
}

function factText(item: Detail, field: string): string | null {
  const fact = item.facts.find((row) => row.field === field);
  return typeof fact?.value === "string" && fact.value ? fact.value : null;
}

function day(iso: string): string {
  return new Intl.DateTimeFormat("en", { dateStyle: "medium" }).format(new Date(iso));
}

function callHeading(item: Detail): string | null {
  if (!item.call_id) return null;
  const title = factText(item, "call_title");
  const count = factNumber(item, "call_topics_count");
  const named = title ? ` — ${title}` : "";
  const many = count != null ? ` (${t("topicCount").replace("{count}", String(count))})` : "";
  return `${t("partOfCall")} ${item.call_id}${named}${many}. ${t("applyToTopic")}`;
}

function grantLine(item: Detail): string | null {
  if (!item.topic_id) return null;
  const grants = factNumber(item, "expected_grants");
  const low = item.amount_min_eur;
  const high = item.amount_max_eur;
  const each =
    low != null && high != null
      ? low === high
        ? money(low)
        : `${money(low)}–${money(high)}`
      : low != null
        ? money(low)
        : high != null
          ? money(high)
          : null;
  if (grants != null && each) {
    return t("projectsEach").replace("{count}", String(grants)).replace("{each}", each);
  }
  if (grants != null) return t("projectsExpected").replace("{count}", String(grants));
  if (each) return t("contributionEach").replace("{each}", each);
  return null;
}

function ScrapedFrom({ item }: { item: Detail }) {
  const notes = [
    ["deadline_at", t("scrapedDeadline")],
    ["budget", t("scrapedBudget")],
  ] as const;
  const lines = notes.flatMap(([field, label]) => {
    const fact = item.facts.find((row) => row.field === field && row.origin === "scraped" && row.quote);
    if (!fact) return [];
    const href = fact.document_url || item.url;
    return [{ label, href, quote: fact.quote }];
  });
  if (!lines.length) return null;
  return (
    <ul className="space-y-1 text-sm text-muted-foreground">
      {lines.map((line) => (
        <li key={line.label}>
          <a href={line.href} title={line.quote ?? undefined} className="underline">
            {line.label}
          </a>
        </li>
      ))}
    </ul>
  );
}

function proposalLine(item: Detail): string | null {
  const proposals = factNumber(item, "proposals_submitted");
  if (proposals == null) return null;
  const projects = factNumber(item, "expected_grants");
  if (projects != null) {
    return t("proposalsForProjects")
      .replace("{proposals}", String(proposals))
      .replace("{projects}", String(projects));
  }
  return t("proposalsSubmitted").replace("{proposals}", String(proposals));
}

function trackMessage(item: Detail): string | null {
  const record = item.track_record;
  if (!record || record.status === "ok") return null;
  if (record.source === "ted_awards") {
    if (record.status === "not_loaded") return t("trackRecordTedNotLoaded");
    if (!record.since) return t("trackRecordTedNoMatchUndated");
    return t("trackRecordTedNoMatch").replace("{since}", dateOnly(record.since));
  }
  if (record.status === "not_comparable") return t("trackRecordCordisNotComparable");
  if (record.status === "no_match") return t("trackRecordCordisNoMatch");
  return t("trackRecordCordisNotLoaded");
}

function activityLabel(code: string): string {
  const label = t(`activity${code}`);
  return label === `activity${code}` ? code : label;
}

function programmeLabel(id: string): string {
  if (id === "h2020") return t("programmeH2020");
  if (id === "horizon-europe") return t("programmeHorizon");
  return id;
}

function evidenceLabel(evidence: string | null): string | null {
  if (evidence === "same_topic") return t("trackRecordSameTopic");
  if (evidence === "same_cpv") return t("trackRecordSameCpv");
  if (evidence === "similar_text") return t("trackRecordSimilar");
  return null;
}

function sourceLabel(sourceId: string): string {
  if (sourceId === "ted") return t("sourceTed");
  if (sourceId === "eu-ft") return t("sourceEuFt");
  if (sourceId === "placsp" || sourceId === "placsp-regional") return t("sourcePlacsp");
  if (sourceId === "bdns") return t("sourceBdns");
  if (sourceId === "curated") return t("sourceCurated");
  return sourceId;
}

function attribution(record: TrackRecord): string {
  if (record.source === "ted_awards") return t("attributionTed");
  const date = record.loaded_at ? dateOnly(record.loaded_at) : "—";
  return t("attributionCordis").replace("{date}", date);
}

function dateOnly(iso: string): string {
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeZone: "UTC" }).format(new Date(iso));
}

"use client";

import { ArrowLeft, ChevronDown, SquareArrowOutUpRight } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { LoadingState } from "@/components/loading-state";
import { api } from "@/lib/api";
import { addCompare, comparePath, useCompareIds } from "@/lib/compare";
import { money, when } from "@/lib/format";
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
  evidence: string | null;
  buyer: string | null;
  amount_eur: number | null;
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
  programme_id: string | null;
  funder_id: string | null;
  deadline_at: string | null;
  budget_total_eur: number | null;
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
  updated_at: string | null;
  analysis: { summary: string | null; blocks: Block[]; model: string | null } | null;
  facts: { field: string; value?: string | number | null; origin: string; confidence: number; quote: string | null }[];
  documents: { url: string; name: string | null }[];
  awards: { id: string; title: string; winner: string | null; amount_eur: number | null; url: string }[];
  track_record?: TrackRecord;
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

  useEffect(() => {
    setTrackOpen(false);
    api<Detail>(`/opportunities/${params.id}`)
      .then(setItem)
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
      : money(item.budget_total_eur);
  const deadlineValue =
    closed && item.deadline_at
      ? `${t("closedLabel")} · ${day(item.deadline_at)}`
      : closed
        ? t("closedLabel")
        : when(item.deadline_at);
  const callLine = callHeading(item);
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
        {topic && (
          <div className="space-y-1 text-sm">
            <p>
              {t("topicLabel")} {item.topic_id}
              {item.type_of_action ? ` · ${item.type_of_action}` : ""}
            </p>
            {callLine && <p>{callLine}</p>}
          </div>
        )}
        <h1 className="text-3xl font-semibold tracking-tight">{original ? item.title : item.title_en || item.title}</h1>
        <dl className="grid gap-3 text-sm sm:grid-cols-4">
          <Cell label="Deadline" value={deadlineValue} />
          <Cell label="Budget" value={budgetValue} hint={grantLine(item)} />
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
        {closed && topic && (
          <div className="space-y-1 text-sm text-muted-foreground">
            <p>{t("closedReference")}</p>
            {proposalLine(item) && <p>{proposalLine(item)}</p>}
          </div>
        )}
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <a href={item.url} className="inline-flex bg-primary px-3 py-1.5 text-sm text-primary-foreground">
            {topic ? t("openOnPortal") : t("officialCall")}
          </a>
          {portalNote && <p className="max-w-xl text-xs text-muted-foreground">{portalNote}</p>}
          <p className="text-sm">
            {item.documents?.find((doc) => doc.name === "Partner search") && (
              <>
                <a className="underline" href={item.documents.find((doc) => doc.name === "Partner search")?.url}>
                  Partner search
                </a>
                {" · "}
              </>
            )}
            {!closed && (
              <>
                <a className="underline" href={`${process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"}/opportunities/${item.id}/calendar`}>
                  Add deadline to calendar
                </a>
                {" · "}
              </>
            )}
            <button type="button" className="cursor-pointer underline" onClick={() => openCompare(item.id)}>
              {t("compare")}
            </button>
          </p>
        </div>
        {compareNote && <p className="text-sm text-muted-foreground">{compareNote}</p>}
        {item.language && item.language !== "en" && (
          <button type="button" className="text-sm underline" onClick={() => setOriginal((value) => !value)}>
            {original ? "Show English" : `Translated from ${item.language}. View original`}
          </button>
        )}
        {low && <p className="text-sm text-status-soon">{t("verify")}</p>}
        <p className="flex flex-wrap items-baseline gap-x-4 font-mono text-xs text-muted-foreground">
          <span>{category}</span>
          <span>
            {t("updated")} {item.updated_at ? when(item.updated_at) : "—"}
          </span>
        </p>
      </header>

      {item.analysis?.blocks.map((block) => {
        const source = sourceHref(block);
        return (
          <section key={block.heading} className="space-y-2">
            <h2 className="text-lg font-semibold">{block.heading}</h2>
            <p className="text-sm leading-6">{block.text}</p>
            {source && (
              <a
                href={source}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 border border-border px-2.5 py-1 text-sm hover:bg-muted"
              >
                {t("source")}
                <SquareArrowOutUpRight className="size-3.5" aria-hidden />
              </a>
            )}
          </section>
        );
      })}

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
                        <span className="tabular"> · EUR {project.amount_eur.toLocaleString("en-GB")}</span>
                      ) : null}
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
    <div>
      <dt className="font-mono text-xs text-muted-foreground">{label}</dt>
      <dd className="tabular">{value}</dd>
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

"""Asistente. Sin clave de Anthropic responde solo con campos ya guardados.

No afirma elegibilidad. Con documentos, cita la página. Sin ellos, cita la ficha.
"""

import re
from dataclasses import dataclass, field

from app.assistant.prompt import ELIGIBILITY_LINE
from app.models.opportunity import Opportunity

_ELIGIBILITY_PROMISE = re.compile(
    r"\b(you are eligible|you qualify|we guarantee|garantizamos|sois elegibles|eres elegible)\b",
    re.IGNORECASE,
)
_NEGATION = re.compile(
    r"\b(not|no|never|cannot|can't|won't|isn't|aren't|don't|doesn't)\b",
    re.IGNORECASE,
)


@dataclass
class Answer:
    text: str
    citations: list[dict]
    model: str
    usage: dict = field(default_factory=dict)


def sentence_promises(sentence: str) -> bool:
    match = _ELIGIBILITY_PROMISE.search(sentence)
    if not match:
        return False
    window = sentence[max(0, match.start() - 60) : match.start()]
    return _NEGATION.search(window) is None


def refuses_eligibility_promise(text: str) -> bool:
    parts = re.split(r"(?<=[.!?])\s+", text)
    return not any(sentence_promises(part) for part in parts or [text])


def guard_text(text: str) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text)
    if len(parts) == 1 and not re.search(r"[.!?]", text):
        return ELIGIBILITY_LINE if sentence_promises(text) else text
    guarded = [ELIGIBILITY_LINE if sentence_promises(part) else part for part in parts]
    return " ".join(guarded)


def answer_about_opportunity(
    opp: Opportunity,
    question: str,
    pages: list[dict] | None = None,
    uploads: list[dict] | None = None,
    link_only: list[dict] | None = None,
) -> Answer:
    from app.assistant.client import has_model

    if has_model() and pages:
        remote = _llm(opp, question, pages)
        if remote and refuses_eligibility_promise(remote.text):
            return remote
    return _extractive(opp, question, pages or [], uploads or [], link_only or [])


def rank_pages(pages: list[dict], question: str) -> list[dict]:
    words = {word for word in re.findall(r"[a-z0-9]{4,}", question.lower())}
    scored = []
    for page in pages:
        text = (page.get("text") or "").lower()
        score = sum(1 for word in words if word in text)
        if score:
            scored.append((score, page))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [page for _, page in scored]


_NO_PROMISE = ("eligib", "qualify", "guarantee", "promise", "garant", "elegib", "certain", "applicant")
_ALIASES = {"closing": "close", "deadline": "deadline", "budget": "eur", "summar": " "}
_NOT_IN_CALL = ("draft our proposal", "invent", "page number", "what changed", "documents i must", "weigh")
_UNREAD = ("specification", "pliego", "tender document", "buyer's site", "buyer site")


def _extractive(opp, question: str, pages: list[dict], uploads: list[dict], link_only: list[dict]) -> Answer:
    q = question.lower()
    if link_only and any(phrase in q for phrase in _UNREAD):
        urls = ", ".join(row.get("document_url") or row.get("url") or "" for row in link_only)
        return Answer(
            text=f"The details are in the tender documents: {urls}".strip(),
            citations=[{"url": row.get("document_url"), "label": row.get("name"), "page": None} for row in link_only],
            model="extractive",
        )
    corpus_pages = [*pages, *uploads]
    if corpus_pages:
        ranked = rank_pages(corpus_pages, question)
        if any(word in q for word in _NO_PROMISE):
            extra = ranked[0]["text"][:400] if ranked else ""
            text = f"{extra} This is not a determination of eligibility. Check the official call: {opp.url}".strip()
            return Answer(text=guard_text(text), citations=_cite(ranked[:1], opp), model="extractive")
        if not ranked or any(phrase in q for phrase in _NOT_IN_CALL):
            return Answer(
                text=f"The call text doesn't cover this. Official call: {opp.url}",
                citations=[{"url": opp.url, "label": "Official call"}],
                model="extractive",
            )
        best = ranked[0]
        return Answer(
            text=guard_text(f"{best['text'][:500]} Source: {opp.url}"),
            citations=_cite([best], opp),
            model="extractive",
        )
    return _record_only(opp, question)


def _cite(pages: list[dict], opp: Opportunity) -> list[dict]:
    if not pages:
        return [{"url": opp.url, "label": "Official call"}]
    best = pages[0]
    return [
        {
            "url": best.get("url") or best.get("document_url") or opp.url,
            "label": best.get("name") or best.get("heading") or "Call document",
            "page": best.get("page"),
            "heading": best.get("heading"),
        }
    ]


def _record_only(opp: Opportunity, question: str) -> Answer:
    q = question.lower()
    citations = [{"url": opp.url, "label": "Official call"}]
    if "budget" in q and opp.budget_total_eur is not None:
        amount = float(opp.budget_total_eur)
        shown = f"{int(amount):,}" if amount.is_integer() else f"{amount:,.2f}"
        return Answer(text=f"The budget is EUR {shown}. Official call: {opp.url}", citations=citations, model="extractive")
    submitted = next((fact.value for fact in opp.facts if fact.field == "proposals_submitted"), None)
    if submitted is not None and any(word in q for word in ("proposal", "submitted", "applied")):
        return Answer(
            text=f"{submitted} proposals were submitted. Official call: {opp.url}",
            citations=citations,
            model="extractive",
        )
    blocks = list(opp.analysis.blocks) if opp.analysis else []
    corpus = " ".join(
        [opp.summary_en or "", opp.description or ""] + [block.text for block in blocks]
    ).lower()
    if any(word in q for word in _NO_PROMISE):
        extra = next((block.text for block in blocks if block.heading.lower() == "eligibility"), "")
        text = (
            f"{extra} This is not a determination of eligibility. "
            f"Check the official call: {opp.url}"
        ).strip()
        return Answer(text=text, citations=citations, model="extractive")
    alias_hit = any(key in q and (not value.strip() or value.strip() in corpus) for key, value in _ALIASES.items())
    if "official" in q or "where is" in q:
        alias_hit = True
    if any(phrase in q for phrase in _NOT_IN_CALL) or not (
        alias_hit or any(word in corpus for word in re.findall(r"[a-z]{5,}", q))
    ):
        return Answer(
            text=f"The call doesn't say. Official call: {opp.url}",
            citations=citations,
            model="extractive",
        )
    summary = opp.analysis.summary if opp.analysis and opp.analysis.summary else opp.summary_en or opp.title
    return Answer(text=f"{summary} Source: {opp.url}", citations=citations, model="extractive")


def answer_general(question: str, items: list[Opportunity]) -> Answer:
    """Sin modelo: glosario y, si no, títulos del índice. Las adjudicaciones no salen."""
    from app.catalog import read_yaml_list
    from app.settings import settings

    stop = {"what", "when", "where", "which", "this", "that", "with", "from", "your", "have", "will", "does"}
    words = {w.lower() for w in re.findall(r"[A-Za-zÀ-ÿ]{3,}", question) if w.lower() not in stop}
    entries = read_yaml_list(settings.config_dir / "knowledge" / "glossary.yaml")
    hits = []
    for entry in entries:
        keys = [str(key).lower() for key in entry.get("keywords") or []]
        keys.append(entry.get("title", "").lower())
        if any(word in " ".join(keys) or word in keys for word in words):
            hits.append(entry)
    if hits:
        entry = hits[0]
        return Answer(
            text=entry["text"].strip(),
            citations=[{"url": entry.get("source"), "label": entry.get("title")}],
            model="knowledge",
        )
    ranked = []
    for item in items:
        if not item.searchable():
            continue
        blob = " ".join([item.title, item.title_en or "", item.summary_en or ""]).lower()
        score = sum(1 for word in re.findall(r"[a-z]{5,}", question.lower()) if word in blob)
        if score:
            ranked.append((score, item))
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    if not ranked:
        return Answer(
            text="I didn't find a call about that. Try other words or the search filters.",
            citations=[],
            model="extractive",
        )
    lines, citations = [], []
    for _, item in ranked[:3]:
        lines.append(f"{item.title_en or item.title} — {item.url}")
        citations.append({"url": item.url, "label": item.title_en or item.title, "id": item.id})
    return Answer(text="\n".join(lines), citations=citations, model="extractive")


def _llm(opp: Opportunity, question: str, pages: list[dict]) -> Answer | None:
    """Una sola llamada, sin herramientas. El chat con documentos usa `chat.complete`."""
    from app.assistant.client import assistant_client, call_kwargs
    from app.assistant.prompt import build_request
    from app.settings import settings

    attached = [
        {
            "name": "Call document",
            "opportunity_id": opp.id,
            "pages": pages,
            "document_url": opp.url,
        }
    ]
    request = build_request(opp, question, attached, [], [])
    try:
        client = assistant_client()
        if client is None:
            return None
        msg = client.messages.create(**call_kwargs(request, max_tokens=700))
        text = "".join(block.text for block in msg.content if getattr(block, "text", None)).strip()
    except Exception as exc:  # noqa: BLE001  sin modelo se usa la respuesta extractiva
        print(f"[assistant] skip: {exc}")
        return None
    if not text:
        return None
    return Answer(
        text=guard_text(text),
        citations=[{"url": opp.url, "label": "Official call"}],
        model=settings.assistant_answer_model,
    )

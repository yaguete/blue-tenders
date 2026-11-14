"""Una pregunta, con la conversación guardada en el servidor.

El cliente manda el mensaje nuevo. El historial lo reconstruye el servidor,
así que no se pueden inyectar respuestas falsas del asistente.
"""

import re
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from uuid import uuid4

from fastapi import HTTPException

from app.assistant.budget import cost_usd, pack
from app.assistant.client import assistant_client, call_kwargs, has_model, uses_deepseek
from app.assistant.documents import load_ready, prepare
from app.assistant.engine import Answer, answer_about_opportunity, answer_general, guard_text
from app.assistant.prompt import (
    ELIGIBILITY_LINE,
    build_request,
    page_from_citation,
    partners_note,
    today_note,
)
from app.assistant.tools import MAX_ROUNDS, dump, run_tool, tool_specs
from app.settings import settings

HISTORY_LIMIT = 12
_SENTENCE = re.compile(r"[.!?]\s|\n")
_NOT_FOUND = "I didn't find a call about that. Try other words or the search filters."
# Lo que el panel enseña mientras una herramienta trabaja. La clave viaja en el SSE.
_STATUS = {
    "search_opportunities": "searching",
    "get_opportunity": "reading",
    "search_knowledge": "glossary",
    "list_funders": "funders",
    "search_documents": "documents",
    "web_search": "web",
}


def prepare_turn(store, user_id: str, body: dict) -> dict:
    question = (body.get("message") or body.get("question") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question required")
    if len(question) > 4000:
        raise HTTPException(status_code=413, detail="Question too long")
    if store.spent_today(date.today().isoformat()) >= settings.assistant_daily_budget_usd:
        raise HTTPException(status_code=429, detail="Assistant is paused: daily budget reached")
    _charge(store, user_id)
    opportunity_id = body.get("opportunity_id") or None
    conversation_id = body.get("conversation_id") or uuid4().hex
    history = store.messages_for(conversation_id)
    if history and history[0].get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    bound = next((row.get("opportunity_id") for row in history if row.get("opportunity_id")), None)
    if bound and opportunity_id and bound != opportunity_id:
        raise HTTPException(status_code=409, detail="This conversation is about another call")
    if bound and not opportunity_id:
        opportunity_id = bound
    item = None
    if opportunity_id:
        item = store.get(opportunity_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Opportunity not found")
        prepare(store, item, background=True)
    upload_ids = list(body.get("upload_ids") or [])
    uploads = _uploads(store, user_id, upload_ids)
    if upload_ids:
        store.bind_uploads(user_id, upload_ids, conversation_id)
    return {
        "question": question,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "opportunity_id": opportunity_id,
        "item": item,
        "history": history[-HISTORY_LIMIT:],
        "uploads": uploads,
        "today": today_note(body.get("today"), body.get("timezone")),
        "partners": _partners(store, item) if item is not None else "",
    }


def _partners(store, item) -> str:
    """Lo mismo que la ficha: historial, consorcios que acaban y quién ganó.

    Lee el historial guardado, como la ficha. Si algo falla, el chat sigue sin ese bloque.
    """
    try:
        from app.models.opportunity import OpportunityKind
        from app.partners.track_record import ending_soon_for, track_record_for
        from app.vertical import load_vertical

        vertical = load_vertical()
        track = track_record_for(item, store, vertical)
        # La ficha solo enseña quién acaba en una subvención.
        ending = ending_soon_for(item, store, vertical, track=track) if item.kind == OpportunityKind.grant else None
        return partners_note(track, ending, store.awards_for(item.call_id))
    except Exception as exc:  # noqa: BLE001  el chat no cae por el historial
        print(f"[assistant] partners skip: {exc}")
        return ""


@dataclass
class _Outcome:
    """Lo que se guarda del turno. `parts` es solo el texto que el usuario se queda."""

    parts: list[str] = field(default_factory=list)
    citations: list[dict] = field(default_factory=list)
    model: str = "extractive"
    usage: dict = field(default_factory=dict)
    answered: bool = False
    ticks: int = 0


class _Sentences:
    """Suelta una frase en cuanto está escrita. El resto espera en el buffer."""

    def __init__(self) -> None:
        self.buffer = ""
        self.parts: list[str] = []

    def feed(self, text: str) -> Iterator[dict]:
        self.buffer += text
        while True:
            match = _SENTENCE.search(self.buffer)
            if not match:
                return
            sentence = self.buffer[: match.end()]
            self.buffer = self.buffer[match.end() :]
            yield from self._push(sentence, spaced=True)

    def flush(self) -> Iterator[dict]:
        if self.buffer:
            yield from self._push(self.buffer, spaced=False)
        self.buffer = ""

    def reset(self) -> None:
        self.buffer = ""
        self.parts.clear()

    def _push(self, sentence: str, *, spaced: bool) -> Iterator[dict]:
        if _bad(sentence):
            shown = ELIGIBILITY_LINE + (" " if spaced else "")
        else:
            shown = sentence
        self.parts.append(shown)
        yield {"type": "delta", "text": shown}


def iter_events(store, turn: dict) -> Iterator[dict]:
    started = time.monotonic()
    outcome = _Outcome()
    item = turn["item"]
    readable, links = ([], [])
    if item is not None:
        readable, links = load_ready(store, item)
    upload_docs = [
        {
            "id": upload["id"],
            "name": upload["name"],
            "document_url": f"upload:{upload['id']}",
            "opportunity_id": turn["opportunity_id"] or "upload",
            "pages": upload["pages"],
            "status": "ok",
        }
        for upload in turn["uploads"]
    ]
    attached, searchable = pack([*readable, *upload_docs])
    if has_model():
        yield from _model_events(store, turn, attached, searchable, links, outcome)
    if not outcome.answered:
        offline = _offline(store, turn, attached, searchable, links)
        text = guard_text(offline.text).strip() or ELIGIBILITY_LINE
        yield from _bridge(outcome, _sentence_deltas(text))
        outcome.citations = offline.citations
        outcome.model = offline.model
        outcome.usage = offline.usage
    stored = guard_text("".join(outcome.parts)).strip()
    if not stored:
        stored = ELIGIBILITY_LINE
        yield _mark(outcome, {"type": "delta", "text": stored})
    answer = Answer(
        text=stored,
        citations=outcome.citations,
        model=outcome.model,
        usage=outcome.usage,
    )
    _remember(store, turn, answer, int((time.monotonic() - started) * 1000))
    for citation in answer.citations:
        yield {"type": "citation", **citation}
    yield {
        "type": "done",
        "conversation_id": turn["conversation_id"],
        "model": answer.model,
        "citations": answer.citations,
        "cost_usd": answer.usage.get("cost_usd", 0),
        "usage": answer.usage,
    }


def _sentence_deltas(text: str) -> Iterator[dict]:
    sentences = _Sentences()
    yield from sentences.feed(text)
    yield from sentences.flush()


def _mark(outcome: _Outcome, event: dict) -> dict:
    outcome.ticks += 1
    if event.get("type") == "reset":
        outcome.parts.clear()
    elif event.get("type") == "delta" and event.get("text"):
        outcome.parts.append(str(event["text"]))
    return event


def _bridge(outcome: _Outcome, source: Iterator[dict]) -> Iterator[dict]:
    """Pasa los eventos y devuelve el valor de retorno del generador de origen."""
    while True:
        try:
            event = next(source)
        except StopIteration as stop:
            return stop.value
        yield _mark(outcome, event)


def _offline(store, turn: dict, attached, searchable, links) -> Answer:
    item = turn["item"]
    if item is None:
        return answer_general(turn["question"], store.opportunities())
    pages = [
        {**page, "name": doc.get("name"), "url": doc.get("document_url")}
        for doc in attached + searchable
        for page in doc.get("pages") or []
    ]
    return answer_about_opportunity(item, turn["question"], pages=pages, uploads=[], link_only=links)


def _bad(sentence: str) -> bool:
    from app.assistant.engine import sentence_promises

    return sentence_promises(sentence)


def _model_events(store, turn, attached, searchable, links, outcome: _Outcome) -> Iterator[dict]:
    try:
        client = assistant_client()
        if client is None:
            raise RuntimeError("no assistant model")
        if turn["item"] is None or searchable:
            yield from _tools_events(client, store, turn, attached, searchable, outcome)
        else:
            yield from _documents_events(client, turn, attached, links, outcome)
    except Exception as exc:  # noqa: BLE001  si el modelo falla, se responde con lo ya guardado
        print(f"[assistant] skip: {exc}")
        if outcome.parts:
            outcome.answered = True


def _documents_events(client, turn, attached, links, outcome: _Outcome) -> Iterator[dict]:
    request = build_request(
        turn["item"],
        turn["question"],
        attached,
        turn["history"],
        [],
        turn.get("today") or "",
        turn.get("partners") or "",
    )
    if links:
        names = ", ".join(f"{row.get('name')} ({row.get('document_url')})" for row in links)
        request["messages"][0]["content"].insert(
            -1,
            {
                "type": "text",
                "text": (
                    f"Linked only, not in your context: {names}. "
                    "If the user asks about their content, say it is in those documents and give the link."
                ),
            },
        )
    sentences = _Sentences()
    final = None
    for tools in ([_WEB_SEARCH], None):
        started = outcome.ticks
        try:
            step = yield from _bridge(
                outcome,
                _consume_stream(
                    client,
                    call_kwargs(request, max_tokens=1400, tools=tools),
                    sentences,
                    drop_text_after_tool=False,
                ),
            )
            final = step["message"]
            break
        except Exception as exc:  # noqa: BLE001  un modelo sin esa herramienta responde igual
            print(f"[assistant] web search off: {exc}")
            if outcome.ticks != started or sentences.buffer:
                break
            if tools is None:
                final = client.messages.create(**call_kwargs(request, max_tokens=1400, tools=None))
                yield from _bridge(outcome, sentences.feed(_message_text(final)))
                break
    yield from _bridge(outcome, sentences.flush())
    outcome.citations = _document_citations(final, turn["item"])
    outcome.model = settings.assistant_answer_model
    outcome.usage = _usage(getattr(final, "usage", None))
    outcome.answered = True


_WEB_SEARCH = {"type": "web_search_20250305", "name": "web_search", "max_uses": 3}


def _document_citations(final, item) -> list[dict]:
    citations = []
    for block in getattr(final, "content", []) or []:
        for citation in getattr(block, "citations", None) or []:
            raw = citation if isinstance(citation, dict) else citation.model_dump()
            citations.append(
                {
                    "label": raw.get("document_title"),
                    "page": page_from_citation(raw),
                    "quote": raw.get("cited_text"),
                    "url": item.url,
                }
            )
    if not citations:
        citations = [{"url": item.url, "label": "Official call"}]
    return citations


def _tools_events(client, store, turn, attached, searchable, outcome: _Outcome) -> Iterator[dict]:
    specs = tool_specs(include_documents=bool(searchable))
    request = build_request(
        turn["item"],
        turn["question"],
        attached,
        turn["history"],
        searchable,
        turn.get("today") or "",
        turn.get("partners") or "",
    )
    messages = request["messages"]
    items = store.opportunities()
    sentences = _Sentences()
    final = None
    for _ in range(MAX_ROUNDS):
        kwargs = call_kwargs(
            {"system": request["system"], "messages": messages},
            max_tokens=900,
            tools=specs,
        )
        started = outcome.ticks
        try:
            step = yield from _bridge(
                outcome,
                _consume_stream(client, kwargs, sentences, drop_text_after_tool=True),
            )
        except Exception as exc:  # noqa: BLE001  sin stream se pide el mensaje entero
            print(f"[assistant] stream off: {exc}")
            if outcome.ticks != started or sentences.buffer:
                yield from _bridge(outcome, sentences.flush())
                outcome.answered = True
                outcome.model = settings.assistant_answer_model
                return
            step = yield from _bridge(outcome, _consume_create(client, kwargs, sentences))
        final = step["message"]
        uses = _tool_uses(final)
        if not uses:
            yield from _bridge(outcome, sentences.flush())
            break
        if sentences.parts:
            yield _mark(outcome, {"type": "reset"})
        sentences.reset()
        if not step["announced"]:
            for block in uses:
                key = _STATUS.get(getattr(block, "name", ""), "")
                if key:
                    yield {"type": "status", "key": key}
        messages.append({"role": "assistant", "content": final.content})
        messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": dump(run_tool(block.name, dict(block.input), items, searchable)),
                    }
                    for block in uses
                ],
            }
        )
    else:
        yield from _bridge(outcome, sentences.flush())
    # Se agotaron las rondas buscando. Una última llamada, sin herramientas, escribe con lo ya encontrado.
    if not "".join(outcome.parts).strip() and len(messages) > 1:
        closing = yield from _answer_without_tools(client, request, messages, sentences, outcome)
        if closing is not None:
            final = closing
    if not "".join(outcome.parts).strip():
        yield _mark(outcome, {"type": "delta", "text": _NOT_FOUND})
    outcome.model = settings.assistant_answer_model
    outcome.usage = _usage(getattr(final, "usage", None))
    outcome.answered = True


def _answer_without_tools(client, request: dict, messages: list, sentences: _Sentences, outcome: _Outcome):
    kwargs = call_kwargs(
        {"system": request["system"], "messages": messages},
        max_tokens=900,
        tools=None,
    )
    started = outcome.ticks
    try:
        step = yield from _bridge(
            outcome,
            _consume_stream(client, kwargs, sentences, drop_text_after_tool=False),
        )
    except Exception as exc:  # noqa: BLE001  sin stream se pide el mensaje entero
        print(f"[assistant] stream off: {exc}")
        if outcome.ticks != started or sentences.buffer:
            yield from _bridge(outcome, sentences.flush())
            return None
        step = yield from _bridge(outcome, _consume_create(client, kwargs, sentences))
    yield from _bridge(outcome, sentences.flush())
    return step["message"]


def _consume_stream(
    client,
    kwargs: dict,
    sentences: _Sentences,
    *,
    drop_text_after_tool: bool,
) -> Iterator[dict]:
    """Suelta frases según llegan. Una herramienta avisa y puede tirar el preámbulo."""
    manager = client.messages.stream(**kwargs)
    stream = manager.__enter__()
    announced = False
    saw_tool = False
    try:
        for event in stream:
            kind, payload = _classify(event)
            if kind in {"tool", "web"}:
                if sentences.parts:
                    yield {"type": "reset"}
                sentences.reset()
                if drop_text_after_tool and kind == "tool":
                    saw_tool = True
                key = "web" if kind == "web" else _STATUS.get(payload, "")
                if key:
                    yield {"type": "status", "key": key}
                    announced = True
            elif kind == "text" and payload and not saw_tool:
                yield from sentences.feed(payload)
        final = stream.get_final_message()
    finally:
        manager.__exit__(None, None, None)
    if not saw_tool and not sentences.parts and not sentences.buffer:
        extra = _message_text(final)
        if extra:
            yield from sentences.feed(extra)
    uses = _tool_uses(final) if drop_text_after_tool else []
    if uses and not saw_tool:
        if sentences.parts:
            yield {"type": "reset"}
        sentences.reset()
        for block in uses:
            key = _STATUS.get(getattr(block, "name", ""), "")
            if key:
                yield {"type": "status", "key": key}
                announced = True
        saw_tool = True
    return {"message": final, "announced": announced, "saw_tool": saw_tool}


def _consume_create(client, kwargs: dict, sentences: _Sentences) -> Iterator[dict]:
    """El mismo turno, de una vez, cuando el proveedor no sabe hacer stream."""
    final = client.messages.create(**kwargs)
    uses = _tool_uses(final)
    if uses:
        for block in uses:
            key = _STATUS.get(getattr(block, "name", ""), "")
            if key:
                yield {"type": "status", "key": key}
        return {"message": final, "announced": True, "saw_tool": True}
    text = _message_text(final)
    if text:
        yield from sentences.feed(text)
    return {"message": final, "announced": False, "saw_tool": False}


def _classify(event) -> tuple[str, str]:
    etype = getattr(event, "type", None)
    if etype == "content_block_delta":
        delta = getattr(event, "delta", None)
        if getattr(delta, "type", None) == "text_delta":
            return "text", getattr(delta, "text", "") or ""
        return "ignore", ""
    if etype == "content_block_start":
        block = getattr(event, "content_block", None)
        name = getattr(block, "name", "") or ""
        if getattr(block, "type", None) == "tool_use":
            return "tool", name
        if getattr(block, "type", None) == "server_tool_use" and name == "web_search":
            return "web", name
    return "ignore", ""


def _tool_uses(final) -> list:
    return [
        block
        for block in getattr(final, "content", []) or []
        if getattr(block, "type", None) == "tool_use"
    ]


def _message_text(final) -> str:
    return "".join(
        block.text
        for block in getattr(final, "content", []) or []
        if getattr(block, "text", None)
    )


def _usage(usage) -> dict:
    if usage is None:
        return {"cost_usd": 0}
    raw = usage if isinstance(usage, dict) else usage.model_dump()
    payload = {
        "input_tokens": int(raw.get("input_tokens") or 0),
        "output_tokens": int(raw.get("output_tokens") or 0),
        "cache_write_tokens": int(raw.get("cache_creation_input_tokens") or 0),
        "cache_read_tokens": int(raw.get("cache_read_input_tokens") or 0),
    }
    server = raw.get("server_tool_use") or {}
    if not isinstance(server, dict):
        server = server.model_dump() if hasattr(server, "model_dump") else {}
    payload["cost_usd"] = cost_usd(
        payload["input_tokens"],
        payload["output_tokens"],
        payload["cache_write_tokens"],
        payload["cache_read_tokens"],
        provider="deepseek" if uses_deepseek() else "anthropic",
        model=settings.assistant_answer_model,
        searches=int(server.get("tool_search") or 0),
    )
    return payload


def _remember(store, turn: dict, answer: Answer, latency_ms: int) -> None:
    base = {
        "conversation_id": turn["conversation_id"],
        "user_id": turn["user_id"],
        "opportunity_id": turn["opportunity_id"],
    }
    store.add_message({**base, "id": uuid4().hex, "role": "user", "text": turn["question"][:4000]})
    store.add_message(
        {
            **base,
            "id": uuid4().hex,
            "role": "assistant",
            "text": answer.text[:8000],
            "citations": answer.citations,
            "model": answer.model,
            "latency_ms": latency_ms,
            **{key: answer.usage.get(key) for key in (
                "input_tokens",
                "output_tokens",
                "cache_read_tokens",
                "cache_write_tokens",
                "cost_usd",
            )},
        }
    )


def _uploads(store, user_id: str, upload_ids: list[str]) -> list[dict]:
    found = []
    for upload_id in upload_ids:
        row = store.upload(upload_id)
        if row is None or row.get("user_id") != user_id:
            raise HTTPException(status_code=404, detail="Upload not found")
        found.append({**row, "pages": store.upload_pages(upload_id)})
    return found


def _charge(store, user_id: str) -> None:
    day = date.today().isoformat()
    count = store.usage_count(user_id, day)
    if count >= settings.assistant_daily_limit:
        raise HTTPException(status_code=429, detail="Daily assistant limit reached")
    store.set_usage(user_id, day, count + 1)

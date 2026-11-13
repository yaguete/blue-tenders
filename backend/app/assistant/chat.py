"""Una pregunta, con la conversación guardada en el servidor.

El cliente manda el mensaje nuevo. El historial lo reconstruye el servidor,
así que no se pueden inyectar respuestas falsas del asistente.
"""

import re
import time
from collections.abc import Iterator
from datetime import date
from uuid import uuid4

from fastapi import HTTPException

from app.assistant.budget import cost_usd, pack
from app.assistant.client import assistant_client, call_kwargs, has_model, uses_deepseek
from app.assistant.documents import load_ready, prepare
from app.assistant.engine import Answer, answer_about_opportunity, answer_general, guard_text
from app.assistant.prompt import ELIGIBILITY_LINE, build_request, page_from_citation, today_note
from app.assistant.tools import dump, run_tool, tool_specs
from app.settings import settings

HISTORY_LIMIT = 12
_SENTENCE = re.compile(r"[.!?]\s|\n")


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
    }


def iter_events(store, turn: dict) -> Iterator[dict]:
    started = time.monotonic()
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
        answer = _with_model(store, turn, attached, searchable, links)
    elif item is not None:
        pages = []
        for doc in attached + searchable:
            for page in doc.get("pages") or []:
                pages.append({**page, "name": doc.get("name"), "url": doc.get("document_url")})
        answer = answer_about_opportunity(
            item, turn["question"], pages=pages, uploads=[], link_only=links
        )
    else:
        answer = answer_general(turn["question"], store.opportunities())
    answer.text = guard_text(answer.text)
    if not answer.text:
        answer = Answer(text=ELIGIBILITY_LINE, citations=answer.citations, model=answer.model, usage=answer.usage)
    pending = []
    if item is not None:
        pending = [
            row.get("name") or "document"
            for row in store.document_files_for(item.id)
            if row.get("status") in {"fetching", "failed"}
        ]
    if pending and "still loading" not in answer.text and "could not read" not in answer.text:
        names = ", ".join(pending)
        answer.text = f"I have not read yet: {names}. {answer.text}"
    _remember(store, turn, answer, int((time.monotonic() - started) * 1000))
    yield from _emit(answer, turn["conversation_id"])


def _emit(answer: Answer, conversation_id: str) -> Iterator[dict]:
    buffer = ""
    for piece in _pieces(answer.text):
        buffer += piece
        while True:
            match = _SENTENCE.search(buffer)
            if not match:
                break
            sentence = buffer[: match.end()]
            buffer = buffer[match.end() :]
            yield {"type": "delta", "text": ELIGIBILITY_LINE + " " if _bad(sentence) else sentence}
    if buffer:
        yield {"type": "delta", "text": ELIGIBILITY_LINE if _bad(buffer) else buffer}
    for citation in answer.citations:
        yield {"type": "citation", **citation}
    yield {
        "type": "done",
        "conversation_id": conversation_id,
        "model": answer.model,
        "citations": answer.citations,
        "cost_usd": answer.usage.get("cost_usd", 0),
        "usage": answer.usage,
    }


def _pieces(text: str) -> list[str]:
    if len(text) <= 80:
        return [text]
    return [text[index : index + 80] for index in range(0, len(text), 80)]


def _bad(sentence: str) -> bool:
    from app.assistant.engine import sentence_promises

    return sentence_promises(sentence)


def _with_model(store, turn: dict, attached, searchable, links) -> Answer:
    item = turn["item"]
    try:
        client = assistant_client()
        if client is None:
            raise RuntimeError("no assistant model")
        if item is None or searchable:
            return _tools(client, store, turn, attached, searchable)
        return _documents(client, turn, attached, links)
    except Exception as exc:  # noqa: BLE001  si el modelo falla, se responde con lo ya guardado
        print(f"[assistant] skip: {exc}")
        if item is None:
            return answer_general(turn["question"], store.opportunities())
        pages = [
            {**page, "name": doc.get("name"), "url": doc.get("document_url")}
            for doc in attached
            for page in doc.get("pages") or []
        ]
        return answer_about_opportunity(item, turn["question"], pages=pages, link_only=links)


def _documents(client, turn: dict, attached, links) -> Answer:
    request = build_request(
        turn["item"], turn["question"], attached, turn["history"], [], turn.get("today") or ""
    )
    if links:
        names = ", ".join(f"{row.get('name')} ({row.get('document_url')})" for row in links)
        request["messages"][0]["content"].insert(
            -1,
            {"type": "text", "text": f"Not read, link only: {names}. Say so if the user asks about them."},
        )
    citations = []
    text, final = _stream_documents(client, request)
    for block in getattr(final, "content", []) or []:
        for citation in getattr(block, "citations", None) or []:
            raw = citation if isinstance(citation, dict) else citation.model_dump()
            citations.append(
                {
                    "label": raw.get("document_title"),
                    "page": page_from_citation(raw),
                    "quote": raw.get("cited_text"),
                    "url": turn["item"].url,
                }
            )
    usage = _usage(getattr(final, "usage", None))
    if not citations:
        citations = [{"url": turn["item"].url, "label": "Official call"}]
    return Answer(text=text.strip(), citations=citations, model=settings.assistant_answer_model, usage=usage)


_WEB_SEARCH = {"type": "web_search_20250305", "name": "web_search", "max_uses": 3}


def _stream_documents(client, request: dict):
    """El documento entero primero. Si el modelo puede, busca en la web cuando no alcance."""
    try:
        return _read_stream(client, request, tools=[_WEB_SEARCH])
    except Exception as exc:  # noqa: BLE001  un modelo sin esa herramienta responde igual
        print(f"[assistant] web search off: {exc}")
        return _read_stream(client, request, tools=None)


def _read_stream(client, request: dict, tools):
    with client.messages.stream(**call_kwargs(request, max_tokens=1400, tools=tools)) as stream:
        text = "".join(stream.text_stream)
        return text, stream.get_final_message()


def _tools(client, store, turn, attached, searchable) -> Answer:
    specs = tool_specs(include_documents=bool(searchable))
    request = build_request(
        turn["item"] or _bare(turn["question"]),
        turn["question"],
        attached,
        turn["history"],
        searchable,
        turn.get("today") or "",
    )
    messages = request["messages"]
    items = store.opportunities()
    final = None
    for _ in range(4):
        final = client.messages.create(
            **call_kwargs(
                {"system": request["system"], "messages": messages},
                max_tokens=900,
                tools=specs,
            )
        )
        uses = [block for block in final.content if getattr(block, "type", None) == "tool_use"]
        if not uses:
            break
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
    text = "".join(block.text for block in final.content if getattr(block, "text", None)).strip()
    return Answer(
        text=text or "I couldn't find this in the indexed sources.",
        citations=[],
        model=settings.assistant_answer_model,
        usage=_usage(getattr(final, "usage", None)),
    )


def _bare(question: str):
    from app.models.opportunity import Opportunity

    return Opportunity(
        id="general",
        source_id="assistant",
        external_id="general",
        url="",
        title="General question",
        description=question,
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

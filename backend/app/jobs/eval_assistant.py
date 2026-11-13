"""Puntúa el modo sin API. Con clave, no sustituye el juicio: solo mira promesas y citas.

uv run python -m app.jobs.eval_assistant
"""

from pathlib import Path

import yaml

from app.assistant.engine import answer_about_opportunity, refuses_eligibility_promise
from app.models.opportunity import Analysis, AnalysisBlock, Citation, Opportunity
from app.store import get_store

QUESTIONS = Path(__file__).resolve().parents[2] / "evals" / "assistant" / "questions.yaml"


def _sample() -> Opportunity:
    stored = get_store().opportunities()
    if stored:
        return stored[0]
    return Opportunity(
        id="eval",
        source_id="eval",
        external_id="eval",
        url="https://example.test/call",
        title="Sample call",
        summary_en="Pre-proposal deadline is stated in the official text.",
        analysis=Analysis(
            summary="Pre-proposal deadline is stated in the official text.",
            blocks=[
                AnalysisBlock(
                    heading="Summary",
                    text="Pre-proposal deadline is stated in the official text.",
                    origin="extracted",
                    citations=[Citation(quote="Pre-proposal", document_url="https://example.test/call")],
                )
            ],
        ),
    )


def _answer(item: dict, sample):
    pages = item.get("pages") or []
    if item["mode"] == "opportunity":
        return answer_about_opportunity(sample, item["question"])
    if item["mode"] == "document":
        return answer_about_opportunity(sample, item["question"], pages=pages)
    if item["mode"] == "upload":
        return answer_about_opportunity(sample, item["question"], uploads=pages)
    if item["mode"] == "unread":
        return answer_about_opportunity(sample, item["question"], link_only=item.get("link_only") or [])
    from app.api.assistant import _general

    return _general(item["question"], get_store().opportunities())


def main() -> None:
    from app.settings import settings

    # Esta pasada puntúa el modo extractivo. Con clave, el modelo no sustituye el juicio.
    had_key = bool(settings.anthropic_api_key or settings.deepseek_api_key)
    settings.anthropic_api_key = ""
    settings.deepseek_api_key = ""
    questions = yaml.safe_load(QUESTIONS.read_text(encoding="utf-8"))
    sample = _sample()
    passed = 0
    for item in questions:
        answer = _answer(item, sample)
        ok = refuses_eligibility_promise(answer.text)
        expect = item["expect"]
        lowered = answer.text.lower()
        if expect == "no_promise" and item["mode"] == "opportunity":
            ok = ok and "not a determination" in lowered
        elif expect == "cites":
            ok = ok and bool(answer.citations) and "couldn't find" not in lowered
        elif expect == "in_glossary":
            ok = ok and answer.model == "knowledge"
        elif expect == "not_found" and item["mode"] == "general":
            # Con el índice vacío tiene que decir que no está. Con datos, solo puede citar
            # convocatorias que de verdad estén en el índice: no se inventa una.
            if "couldn't find" not in lowered:
                known = {opp.url for opp in get_store().opportunities()}
                ok = ok and bool(answer.citations) and all(row.get("url") in known for row in answer.citations)
        elif expect == "not_found":
            ok = ok and "couldn't find" in lowered
        elif expect == "page":
            ok = ok and answer.citations and answer.citations[0].get("page") == item["page"]
            ok = ok and "couldn't find" not in lowered
        elif expect == "unread":
            ok = ok and "not read" in lowered
        passed += int(ok)
        print(f"{'ok' if ok else 'FAIL'} {item['id']} {expect} model={answer.model}")
    print(f"{passed}/{len(questions)}")
    if had_key:
        print("cost: not measured in the extractive pass")
    else:
        print("cost: not measured (no API key)")
    if passed != len(questions):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

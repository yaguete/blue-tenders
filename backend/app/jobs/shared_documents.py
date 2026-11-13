"""Descarga una vez los anexos generales de Horizon Europe.

uv run python -m app.jobs.shared_documents
"""

from app.assistant.documents import prepare
from app.models.opportunity import Opportunity
from app.store import get_store


def main() -> None:
    """Un topic de Horizon recibe estos anexos en su contexto. Aquí solo se cargan."""
    carrier = Opportunity(
        id="shared-horizon",
        source_id="eu-ft",
        external_id="annexes",
        url="https://ec.europa.eu/info/funding-tenders/opportunities/portal/",
        title="Horizon Europe general annexes",
        programme_id="horizon-europe",
    )
    rows = prepare(get_store(), carrier, background=False)
    for row in rows:
        if row.get("shared") or row.get("opportunity_id") == "":
            print(f"[annexes] {row.get('name')} {row.get('status')} pages={row.get('pages')}")


if __name__ == "__main__":
    main()

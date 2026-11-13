"""Aides-territoires. Catálogo de ayudas francesas, no un feed de avisos.

La clave (`AIDES_TERRITOIRES_API_KEY`) se cambia por un Bearer de 24 h en
`POST /api/connexion/`. La búsqueda es `GET /api/aids/?text=`. Sin ese
parámetro el API devuelve el catálogo entero: si el total no baja, se aborta.

`since` no recorta. Una ayuda permanente de 2021 sigue abierta, y la marca de
agua de un día la perdería. El corte del sector lo hacen los `search_terms` y,
después, el prefiltro sobre el título y el texto. Un plazo que no es una fecha
no se convierte. El importe no trae moneda: no se publica.
"""

import html
import re
from collections.abc import Iterable
from datetime import date, datetime
from zoneinfo import ZoneInfo

import httpx

from app.models.opportunity import (
    Buyer,
    DeadlineModel,
    Document,
    Opportunity,
    OpportunityKind,
    OpportunityType,
)
from app.settings import settings
from app.sources.base import Source
from app.sources.terms import search_pairs
from app.vertical import Vertical

CONNEXION_URL = "https://aides-territoires.beta.gouv.fr/api/connexion/"
SEARCH_URL = "https://aides-territoires.beta.gouv.fr/api/aids/"
CATALOGUE = "https://aides-territoires.beta.gouv.fr"
_ZONE = ZoneInfo("Europe/Paris")
_PAGE = 50
_MAX_PAGES = 20
_UA = "blue-tender/1.0"
_TAG = re.compile(r"<[^>]+>")
_HREF = re.compile(r"""href=["'](https?://[^"']+)["']""", re.IGNORECASE)
_SPACE = re.compile(r"\s+")
_GRANT = ("subvention",)
_LOAN = ("prêt", "pret", "avance")
_ENGINEERING = ("ingénierie", "ingenierie")


def list_params(term: str, page: int) -> dict[str, str | int]:
    return {"text": term, "itemsPerPage": _PAGE, "page": page}


def filters_bite(filtered_total: int, unfiltered_total: int) -> None:
    """El API ignora un parámetro desconocido y devuelve el catálogo, con un 200."""
    if filtered_total >= unfiltered_total:
        raise RuntimeError("Aides-territoires ha ignorado el filtro: el total no baja")


def aid_kind(types: list[str]) -> OpportunityKind:
    text = " ".join(types).casefold()
    grant = any(word in text for word in _GRANT)
    loan = any(word in text for word in _LOAN)
    if grant and loan:
        return OpportunityKind.blended
    if loan:
        return OpportunityKind.loan
    if grant:
        return OpportunityKind.grant
    if any(word in text for word in _ENGINEERING):
        return OpportunityKind.technical_assistance
    return OpportunityKind.grant


def _plain(value) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    text = _TAG.sub(" ", html.unescape(value))
    return _SPACE.sub(" ", text).strip()


def _when(value) -> datetime | None:
    """Fecha de la API. Un día suelto es medianoche en París. Una frase no es una fecha."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if len(text) == 10:
        try:
            day = date.fromisoformat(text)
        except ValueError:
            return None
        return datetime(day.year, day.month, day.day, tzinfo=_ZONE)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=_ZONE)


def _published(value) -> date | None:
    parsed = _when(value)
    return parsed.date() if parsed else None


def _funder(raw: dict) -> str | None:
    rows = raw.get("financers")
    if isinstance(rows, str):
        return rows.strip() or None
    if not isinstance(rows, list) or not rows:
        return None
    first = rows[0]
    if isinstance(first, str):
        return first.strip() or None
    if isinstance(first, dict) and first.get("name"):
        return str(first["name"]).strip() or None
    return None


def _catalogue_url(raw: dict) -> str:
    path = raw.get("url") if isinstance(raw.get("url"), str) else ""
    if path.startswith("http"):
        return path
    if path.startswith("/"):
        return f"{CATALOGUE}{path}"
    slug = raw.get("slug") or raw.get("id") or ""
    return f"{CATALOGUE}/aides/{slug}/"


def _public(raw: dict) -> dict:
    return {
        key: value
        for key, value in raw.items()
        if "contact" not in key and "email" not in key and "phone" not in key
    }


def _documents(raw: dict, page: str) -> list[Document]:
    documents = []
    seen = set()

    def add(url: str, name: str) -> None:
        if not url.startswith("http") or url in seen or url == page:
            return
        seen.add(url)
        documents.append(Document(url=url, name=name, kind="notice", access="link_only"))

    add(_catalogue_url(raw), "Aides-territoires")
    application = raw.get("application_url")
    if isinstance(application, str):
        add(application, "Application page")
    for field in ("description", "eligibility"):
        blob = raw.get(field)
        if isinstance(blob, str):
            for href in _HREF.findall(blob):
                add(html.unescape(href), "Call document")
    return documents


class AidesTerritoiresSource(Source):
    id = "aides-territoires"
    kind = "api"
    # Busca por término: un cero es un catálogo sin esa frase, no una fuente caída.
    volume_alert = False

    def fetch(self, since: date, vertical: Vertical) -> Iterable[dict]:
        # `since` no filtra: ver el docstring del módulo.
        del since
        pairs = search_pairs(vertical, self.id)
        if not pairs:
            raise ValueError(
                "Aides-territoires: el vertical no tiene search_terms; no se baja el catálogo entero."
            )
        key = settings.aides_territoires_api_key
        if not key:
            raise RuntimeError("Aides-territoires: falta AIDES_TERRITOIRES_API_KEY")
        token = _bearer(key)
        seen: dict[str, dict] = {}
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": _UA,
        }
        with httpx.Client(timeout=40, headers=headers) as client:
            bare = client.get(SEARCH_URL, params={"itemsPerPage": 1, "page": 1})
            bare.raise_for_status()
            unfiltered = int(bare.json().get("count") or 0)
            for _subsector, term in pairs:
                for row in _pages(client, term, unfiltered):
                    if row.get("is_live") is False:
                        continue
                    ident = str(row.get("id") or "")
                    if not ident or ident in seen:
                        continue
                    seen[ident] = _public(row)
        yield from seen.values()

    def to_tender(self, raw: dict) -> Opportunity:
        raw = _public(raw)
        external = str(raw.get("id") or raw.get("slug") or "")
        title = _plain(raw.get("name") or raw.get("name_initial"))
        if not external or not title:
            raise ValueError("ayuda de Aides-territoires sin id o sin título")
        description = "\n\n".join(
            piece
            for piece in (_plain(raw.get("description")), _plain(raw.get("eligibility")))
            if piece
        )
        types = [str(item) for item in raw.get("aid_types") or [] if item]
        kind = aid_kind(types)
        deadline = _when(raw.get("submission_deadline"))
        page = raw.get("origin_url") if isinstance(raw.get("origin_url"), str) else ""
        if not page.startswith("http"):
            page = _catalogue_url(raw)
        funder = _funder(raw)
        audiences = raw.get("targeted_audiences") or []
        if isinstance(audiences, str):
            audiences = [audiences]
        low = _rate(raw.get("subvention_rate_lower_bound"))
        high = _rate(raw.get("subvention_rate_upper_bound"))
        return Opportunity(
            id=Opportunity.make_id(self.id, external),
            source_id=self.id,
            external_id=external,
            url=page,
            type=OpportunityType.grant,
            kind=kind,
            title=title,
            description=description or None,
            buyer=Buyer(name=funder, country="FR") if funder else None,
            country="FR",
            language="fr",
            published_at=_published(raw.get("date_created")),
            opens_at=_when(raw.get("start_date")),
            deadline_at=deadline,
            # El listado ya es solo lo vivo. Sin plazo no se inventa una fecha, y no se cierra
            # a los 90 días: la ficha sigue publicada en el catálogo.
            deadline_model=DeadlineModel.continuous if deadline is None else DeadlineModel.single,
            cofunding_min=low,
            cofunding_max=high,
            eligible_entity_types=[str(item) for item in audiences if item],
            documents=_documents(raw, page),
            raw=raw,
        )


def _rate(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not 0 <= value <= 100:
        return None
    return float(value)


def _bearer(key: str) -> str:
    response = httpx.post(
        CONNEXION_URL,
        headers={"X-AUTH-TOKEN": key, "Accept": "application/json", "User-Agent": _UA},
        timeout=40,
    )
    response.raise_for_status()
    token = (response.json() or {}).get("token")
    if not isinstance(token, str) or not token:
        raise RuntimeError("Aides-territoires no ha devuelto Bearer")
    return token


def _pages(client: httpx.Client, term: str, unfiltered: int) -> list[dict]:
    found: list[dict] = []
    for page in range(1, _MAX_PAGES + 1):
        response = client.get(SEARCH_URL, params=list_params(term, page))
        response.raise_for_status()
        payload = response.json()
        if page == 1:
            filters_bite(int(payload.get("count") or 0), unfiltered)
        rows = payload.get("results") or []
        found.extend(row for row in rows if isinstance(row, dict))
        if not payload.get("next") or len(rows) < _PAGE:
            break
    return found

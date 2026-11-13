"""TED (Tenders Electronic Daily), API de búsqueda v3.

Verificado contra la API en producción el 11 nov 2026. Cosas que no son obvias:

- `fields` no admite comodín: `["*"]` devuelve 400. Hay que enumerar los campos.
- En la búsqueda experta, los valores de `IN (...)` van separados por espacios.
  `IN (a OR b)` devuelve 400.
- `limit` tiene un máximo de 250. Para recorrer muchos resultados se usa el modo
  ITERATION, que devuelve un `iterationNextToken` para la página siguiente.
- Texto completo (`FT`): busca en el anuncio entero, sin distinguir mayúsculas, acentos
  ni guiones.
  - `FT ~ "offshore wind"` es una frase exacta.
  - El comodín va fuera de las comillas: `FT ~ landstrom*`. Dentro no se expande.
  - No hay operador de cercanía: `FT ~ (a NEAR b)` no da error, pero se comporta como
    `FT ~ (a AND b)`, que casa con las dos palabras en cualquier parte del anuncio.
  - Para unir términos se repite la cláusula: `FT ~ "a" OR FT ~ "b"`.
    `FT ~ ("a" OR "b")` devuelve 0 resultados con un 200, sin error.

Se hacen dos tipos de consulta: una por texto completo por cada subsector del vertical y otra
por CPV. El CPV solo cubre algo más de la mitad de los anuncios del sector (un estudio
geotécnico para un parque eólico marino lleva un CPV de ingeniería genérico), y el título solo
rara vez nombra el sector. Lo que entra por texto completo lleva en el registro crudo los
subsectores que lo encontraron (`SOURCE_SUBSECTORS`).
"""

import hashlib
import re
import time
from collections.abc import Iterable, Iterator
from datetime import date, datetime

import httpx

from app.keywords import keyword_words
from app.models.opportunity import Fact, FactOrigin
from app.models.tender import Budget, Buyer, Document, OpportunityType, Tender
from app.sources.base import SOURCE_SUBSECTORS, Source
from app.vertical import Vertical

SEARCH_URL = "https://api.ted.europa.eu/v3/notices/search"
# El PDF de ted.europa.eu responde 429 desde un centro de datos. Estos campos son el texto que la API sí devuelve.
_NOTICE_TEXT_FIELDS = [
    "notice-title",
    "description-proc",
    "description-lot",
    "selection-criterion-description-lot",
    "award-criterion-description-lot",
    "contract-conditions-description-lot",
    "buyer-name",
    "place-of-performance",
    "deadline-receipt-tender-date-lot",
    "estimated-value-proc",
    "official-language",
]
_NOTICE_LABELS = {
    "notice-title": "Title",
    "description-proc": "Description",
    "description-lot": "Lot",
    "selection-criterion-description-lot": "Selection criteria",
    "award-criterion-description-lot": "Award criteria",
    "contract-conditions-description-lot": "Contract conditions",
    "buyer-name": "Buyer",
    "place-of-performance": "Place of performance",
    "deadline-receipt-tender-date-lot": "Deadline",
    "estimated-value-proc": "Estimated value",
}
_NOTICE_ID = re.compile(r"ted\.europa\.eu/.+?/notice/(?:-/(?:detail/)?)?(\d+-\d{4})")
PAGE_SIZE = 250  # máximo que acepta la API
MAX_PAGES = 400  # tope de seguridad: 100.000 anuncios por ejecución

FIELDS = [
    "publication-number",
    "publication-date",
    "notice-type",
    "notice-title",
    "title-proc",
    "description-proc",
    "official-language",
    "buyer-name",
    "buyer-country",
    "classification-cpv",
    "place-of-performance-country-proc",
    "place-of-performance-subdiv-proc",
    "deadline-receipt-tender-date-lot",
    "deadline-receipt-tender-time-lot",
    "estimated-value-proc",
    "estimated-value-cur-proc",
    "procedure-identifier",
    "links",
    "document-url-lot",
    "winner-name",
    "winner-country",
    "winner-identifier",
    "winner-size",
    "result-value-notice",
    "result-value-cur-notice",
]

_CPV = re.compile(r"^\d{8}$")

# TED da los países en ISO 3166-1 alpha-3; el modelo canónico usa alpha-2.
# Un código que no esté aquí se deja vacío: mejor sin país que con uno inventado.
# fmt: off
_COUNTRY_A3_TO_A2 = {
    "AUT": "AT", "BEL": "BE", "BGR": "BG", "HRV": "HR", "CYP": "CY", "CZE": "CZ",
    "DNK": "DK", "EST": "EE", "FIN": "FI", "FRA": "FR", "DEU": "DE", "GRC": "GR",
    "HUN": "HU", "IRL": "IE", "ITA": "IT", "LVA": "LV", "LTU": "LT", "LUX": "LU",
    "MLT": "MT", "NLD": "NL", "POL": "PL", "PRT": "PT", "ROU": "RO", "SVK": "SK",
    "SVN": "SI", "ESP": "ES", "SWE": "SE",
    "NOR": "NO", "ISL": "IS", "LIE": "LI", "CHE": "CH", "GBR": "GB",
    "ALB": "AL", "BIH": "BA", "MDA": "MD", "MKD": "MK", "MNE": "ME", "SRB": "RS",
    "TUR": "TR", "UKR": "UA",
}

# Las lenguas vienen en ISO 639-3; el modelo canónico usa ISO 639-1.
_LANG_A3_TO_A2 = {
    "bul": "bg", "ces": "cs", "dan": "da", "deu": "de", "ell": "el", "eng": "en",
    "spa": "es", "est": "et", "fin": "fi", "fra": "fr", "gle": "ga", "hrv": "hr",
    "hun": "hu", "ita": "it", "lit": "lt", "lav": "lv", "mlt": "mt", "nld": "nl",
    "pol": "pl", "por": "pt", "ron": "ro", "slk": "sk", "slv": "sl", "swe": "sv",
}
# fmt: on


def build_query(since: date, cpv: list[str]) -> str:
    """Consulta de búsqueda experta: anuncios publicados desde `since` con alguno de los CPV."""
    if not cpv:
        raise ValueError("TED: el vertical no tiene códigos CPV; no se consulta todo TED.")
    bad = [c for c in cpv if not _CPV.match(c)]
    if bad:
        raise ValueError(f"TED: códigos CPV no válidos (se esperan 8 dígitos): {bad}")
    return f"classification-cpv IN ({' '.join(cpv)}) AND publication-date>={since:%Y%m%d}"


# Una sigla corta suelta ("OPS") aparece en demasiados anuncios que no tienen nada que ver
# cuando se busca en el texto completo. Se sigue usando en local, sobre el título.
MIN_FULLTEXT_WORD = 5


def fulltext_clause(keyword: str) -> str | None:
    """Cláusula `FT` de TED para una keyword del vertical, o None si no conviene buscarla.

    - Sin comodín: frase exacta. TED ya ignora mayúsculas, acentos, guiones y plurales.
    - Una sola palabra con comodín (`landstrom*`): se busca tal cual.
    - Varias palabras con comodín (`eólic* offshore`): no se busca. TED no tiene comodín dentro
      de una frase ni operador de cercanía (`NEAR` se comporta como `AND`), así que la única
      forma sería `FT ~ (eolic* AND offshore)`, que casa con las dos palabras en cualquier
      parte del anuncio. Medido el 11 nov 2026, eso traía barredoras y combustible de aviación.
      Para estas keywords hay que añadir al vertical la frase escrita entera.
    """
    words = keyword_words(keyword)  # normalizadas: solo letras, cifras y un `*` final
    if not words:
        return None
    if any(w.endswith("*") for w in words):
        return f"FT ~ {words[0]}" if len(words) == 1 else None
    if len(words) == 1 and len(words[0]) < MIN_FULLTEXT_WORD:
        return None
    return f'FT ~ "{" ".join(words)}"'


def build_fulltext_query(since: date, keywords: list[str]) -> str | None:
    """Anuncios desde `since` que mencionan alguna de las keywords en su texto completo."""
    clauses = list(dict.fromkeys(c for c in map(fulltext_clause, keywords) if c))
    if not clauses:
        return None
    # Cada término lleva su propia cláusula: `FT ~ ("a" OR "b")` devuelve 0 sin dar error.
    return f"({' OR '.join(clauses)}) AND publication-date>={since:%Y%m%d}"


def publication_number_from_url(url: str) -> str | None:
    match = _NOTICE_ID.search(url or "")
    return match.group(1) if match else None


def notice_pages(url: str) -> list[dict]:
    """Texto del anuncio vía la API de búsqueda, cuando el PDF de la web no se puede bajar."""
    number = publication_number_from_url(url)
    if not number:
        return []
    try:
        with httpx.Client(timeout=30) as client:
            response = client.post(
                SEARCH_URL,
                json={
                    "query": f"publication-number={number}",
                    "fields": _NOTICE_TEXT_FIELDS,
                    "limit": 1,
                    "scope": "ALL",
                    "paginationMode": "PAGE_NUMBER",
                },
            )
            response.raise_for_status()
        notices = response.json().get("notices") or []
    except (httpx.HTTPError, ValueError):
        return []
    if not notices:
        return []
    record = notices[0]
    lang = (_first(record.get("official-language")) or "").lower() or None
    pages = []
    for field, heading in _NOTICE_LABELS.items():
        text = _all_in_language(record.get(field), lang)
        if text:
            pages.append({"page": len(pages) + 1, "heading": heading, "text": text})
    return pages


def _all_in_language(value, lang: str | None) -> str:
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, list):
        parts = [_all_in_language(item, lang) for item in value]
        return "\n".join(part for part in parts if part)
    if isinstance(value, dict):
        if value and all(isinstance(key, str) and len(key) == 3 for key in value):
            chosen = None
            for key in (lang, "eng"):
                if key and key in value:
                    chosen = value[key]
                    break
            if chosen is None:
                chosen = next(iter(value.values()))
            return _all_in_language(chosen, lang)
        parts = [_all_in_language(item, lang) for item in value.values()]
        return "\n".join(part for part in parts if part)
    return str(value).strip()


def _first(value) -> str | None:
    """Primer elemento de una lista, o el propio valor si no es una lista.

    TED deja entidades HTML en el título (`&#8217;`, `&amp;`). Se decodifican aquí.
    """
    from html import unescape

    if isinstance(value, list):
        text = str(value[0]) if value else None
    else:
        text = str(value) if value not in (None, "") else None
    return unescape(text) if text is not None else None


def _in_language(value, lang: str | None) -> str | None:
    """Texto de un campo multilingüe (`{"swe": "...", "eng": "..."}`) en la lengua pedida.

    Si no está en esa lengua se prueba el inglés y, si tampoco, la primera disponible.
    """
    if not isinstance(value, dict) or not value:
        return None
    for key in (lang, "eng"):
        if key and key in value:
            return _first(value[key])
    return _first(next(iter(value.values())))


def _unique(values) -> list[str]:
    return list(dict.fromkeys(str(v) for v in values or []))


def _http_urls(value) -> list[str]:
    found = []
    if isinstance(value, str) and value.startswith("http"):
        found.append(value)
    elif isinstance(value, list):
        for item in value:
            found.extend(_http_urls(item))
    elif isinstance(value, dict):
        for item in value.values():
            found.extend(_http_urls(item))
    return list(dict.fromkeys(found))


def _documents(pdf: str | None, lot_urls) -> list[Document]:
    """El PDF es el anuncio. Los pliegos (`document-url-lot`) solo se enlazan: no se leen."""
    documents = [Document(url=pdf, name="Notice (PDF)", kind="notice", access="fetch")] if pdf else []
    seen = {pdf} if pdf else set()
    for url in _http_urls(lot_urls):
        if url in seen:
            continue
        seen.add(url)
        documents.append(
            Document(url=url, name="Tender documents", kind="tender_documents", access="link_only")
        )
    return documents


def _deadline(dates, times) -> datetime | None:
    """El plazo más temprano entre los lotes.

    TED da la fecha y la hora en dos listas paralelas, cada una con su desfase horario.
    Si un lote no trae hora se guarda el inicio de ese día: nunca se inventa una hora
    posterior al plazo real.
    """
    dates = dates or []
    times = times if times and len(times) == len(dates) else [None] * len(dates)
    parsed = []
    for d, t in zip(dates, times):
        day = str(d)[:10]
        try:
            if t:
                parsed.append(datetime.fromisoformat(f"{day}T{t}"))
            else:
                offset = str(d)[10:] or "Z"
                parsed.append(datetime.fromisoformat(f"{day}T00:00:00{offset}"))
        except ValueError:
            continue
    return min(parsed) if parsed else None


def _award_eur(raw: dict) -> float | None:
    """Importe adjudicado solo si la fuente dice EUR y es mayor que cero.

    TED usa 0 cuando el importe es confidencial y -1 cuando no lo sabe. Ninguno de los
    dos es un importe.
    """
    if _first(raw.get("result-value-cur-notice")) != "EUR":
        return None
    raw_amount = raw.get("result-value-notice")
    if isinstance(raw_amount, list):
        raw_amount = raw_amount[0] if raw_amount else None
    try:
        value = float(raw_amount)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    return value


def _id_hash(value) -> str | None:
    text = re.sub(r"\s+", "", str(value or "")).upper()
    if not text or text in {"-1", "0"}:
        return None
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _string_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value]
    return [str(value).strip()]


def _winner_names(raw: dict, lang3: str | None) -> list[str]:
    value = raw.get("winner-name")
    if isinstance(value, dict):
        names = None
        for key in (lang3, "eng"):
            if key and isinstance(value.get(key), list):
                names = value[key]
                break
        if names is None:
            names = next((item for item in value.values() if isinstance(item, list)), [])
        return [str(name).strip() for name in names]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _same_length(names: list[str], value) -> list[str] | None:
    items = _string_list(value)
    if len(items) != len(names):
        return None
    return items


def _unanimous_country(value) -> str | None:
    codes = [code for code in _string_list(value) if code]
    if not codes or len({code.upper() for code in codes}) != 1:
        return None
    return _COUNTRY_A3_TO_A2.get(codes[0].upper())


def _winners(raw: dict, lang3: str | None) -> list[dict]:
    """Un adjudicatario por nombre. No empareja país ni identificador si las listas no cuadran."""
    names = _winner_names(raw, lang3)
    if not names:
        return []
    countries = _same_length(names, raw.get("winner-country"))
    sizes = _same_length(names, raw.get("winner-size"))
    identifiers = _same_length(names, raw.get("winner-identifier"))
    shared_country = _unanimous_country(raw.get("winner-country")) if countries is None else None
    rows = []
    seen = set()
    for index, name in enumerate(names):
        if not name or name in seen:
            continue
        seen.add(name)
        country = shared_country
        if countries is not None:
            country = _COUNTRY_A3_TO_A2.get(countries[index].upper())
        size = None
        if sizes is not None and sizes[index]:
            size = sizes[index]
        rows.append(
            {
                "name": name,
                "country": country,
                "size": size,
                "id_hash": _id_hash(identifiers[index]) if identifiers is not None else None,
            }
        )
    return rows


def _type(notice_type: str | None) -> OpportunityType:
    kind = (notice_type or "").split("-")[0]
    if kind == "pin":
        return OpportunityType.prior_information_notice
    if kind == "can":
        return OpportunityType.award
    return OpportunityType.tender


def _budget(raw: dict) -> Budget | None:
    amount = _first(raw.get("estimated-value-proc"))
    if amount is None:
        return None
    try:
        value = float(amount)
    except ValueError:
        return None
    currency = _first(raw.get("estimated-value-cur-proc"))
    return Budget(amount=value, currency=currency, amount_eur=value if currency == "EUR" else None)


def search(client: httpx.Client, payload: dict, retries: int = 3, backoff: float = 2.0) -> dict:
    """Una página de resultados. Reintenta los fallos pasajeros; los 4xx fallan a la primera.

    TED devuelve de vez en cuando un cuerpo vacío o un 5xx; con el cron diario no merece
    perder la ejecución por eso. Un 400 es un error nuestro (consulta o campos) y reintentarlo
    no lo arregla.
    """
    last = "sin respuesta"
    for attempt in range(retries):
        if attempt:
            # Un 429 espera más: TED corta cuando se paginan muchos avisos de adjudicación.
            factor = 3 if str(last).startswith("429") else 1
            time.sleep(backoff * attempt * factor)
        try:
            r = client.post(SEARCH_URL, json=payload)
        except httpx.TransportError as e:
            last = f"error de red: {e}"
            continue
        if r.status_code == 429 or r.status_code >= 500:
            last = f"{r.status_code}: {r.text[:200]}"
            continue
        if r.status_code >= 400:
            # El cuerpo del error de TED dice qué campo o qué parte de la consulta falla.
            raise RuntimeError(f"TED {r.status_code}: {r.text[:500]}")
        try:
            return r.json()
        except ValueError:
            last = f"{r.status_code} con un cuerpo que no es JSON: {r.text[:200]!r}"
    raise RuntimeError(f"TED no responde tras {retries} intentos ({last})")


def _pages(client: httpx.Client, query: str, pause: float = 0.4) -> Iterator[dict]:
    """Todos los anuncios de una consulta, página a página."""
    payload = {
        "query": query,
        "fields": FIELDS,
        "limit": PAGE_SIZE,
        "scope": "ALL",
        "paginationMode": "ITERATION",
    }
    for page in range(MAX_PAGES):
        if page and pause:
            time.sleep(pause)
        data = search(client, payload)
        notices = data.get("notices") or []
        yield from notices
        token = data.get("iterationNextToken")
        if not notices or not token:
            return
        payload["iterationNextToken"] = token
    raise RuntimeError(f"TED: más de {MAX_PAGES} páginas; revisa la consulta.")


class TedSource(Source):
    id = "ted"
    kind = "api"

    def __init__(self, notice_types: tuple[str, ...] | None = None, include_cpv: bool = True):
        self.notice_types = notice_types
        self.include_cpv = include_cpv

    def fetch(self, since: date, vertical: Vertical) -> Iterable[dict]:
        by_text = {
            s.id: build_fulltext_query(since, s.keywords) for s in vertical.active_subsectors
        }
        by_text = {sub: self._scoped(q) for sub, q in by_text.items() if q}
        if not by_text and not (self.include_cpv and vertical.cpv):
            raise ValueError(
                "TED: el vertical no tiene ni CPV ni keywords; no se consulta todo TED."
            )

        with httpx.Client(timeout=30) as client:
            # Primero el texto completo, subsector a subsector, para saber cuál lo encontró.
            found: dict[str, dict] = {}
            for sub, query in by_text.items():
                for notice in _pages(client, query):
                    number = _first(notice.get("publication-number"))
                    if not number:
                        continue
                    found.setdefault(number, notice).setdefault(SOURCE_SUBSECTORS, []).append(sub)
            yield from found.values()

            if self.include_cpv and vertical.cpv:
                for notice in _pages(client, self._scoped(build_query(since, vertical.cpv))):
                    if _first(notice.get("publication-number")) not in found:
                        yield notice

    def _scoped(self, query: str) -> str:
        if not self.notice_types:
            return query
        return f"notice-type IN ({' '.join(self.notice_types)}) AND {query}"

    def to_tender(self, raw: dict) -> Tender:
        ext = _first(raw.get("publication-number"))
        if not ext:
            raise ValueError("anuncio de TED sin publication-number")

        lang3 = (_first(raw.get("official-language")) or "").lower() or None
        titles = raw.get("notice-title")
        title_en = _first(titles["eng"]) if isinstance(titles, dict) and "eng" in titles else None
        title = _in_language(raw.get("title-proc"), lang3) or _in_language(titles, lang3)
        if not title:
            raise ValueError(f"anuncio de TED {ext} sin título")

        buyer_country = _COUNTRY_A3_TO_A2.get(_first(raw.get("buyer-country")) or "")
        buyer_name = _in_language(raw.get("buyer-name"), lang3)
        place_country = _COUNTRY_A3_TO_A2.get(
            _first(raw.get("place-of-performance-country-proc")) or ""
        )

        links = raw.get("links") or {}
        html = (links.get("html") or {}).get("ENG")
        pdf = (links.get("pdf") or {}).get("ENG")
        published = _first(raw.get("publication-date"))
        winners = _winners(raw, lang3)
        award_value = _award_eur(raw)
        facts = []
        if winners:
            facts.append(Fact(field="winners", value=winners, origin=FactOrigin.source, confidence=0.9))
            facts.append(
                Fact(
                    field="winner_name",
                    value=", ".join(row["name"] for row in winners),
                    origin=FactOrigin.source,
                    confidence=0.9,
                )
            )
        if award_value is not None:
            facts.append(
                Fact(field="award_value_eur", value=award_value, origin=FactOrigin.source, confidence=0.9)
            )
        procedure = _first(raw.get("procedure-identifier"))
        return Tender(
            id=Tender.make_id(self.id, ext),
            source_id=self.id,
            external_id=ext,
            url=html or f"https://ted.europa.eu/en/notice/-/detail/{ext}",
            type=_type(_first(raw.get("notice-type"))),
            call_id=procedure,
            facts=facts,
            title=title,
            title_en=title_en,
            description=_in_language(raw.get("description-proc"), lang3),
            buyer=Buyer(name=buyer_name, country=buyer_country) if buyer_name else None,
            country=place_country or buyer_country,
            region=_first(raw.get("place-of-performance-subdiv-proc")),
            cpv=_unique(raw.get("classification-cpv")),
            budget=_budget(raw),
            published_at=date.fromisoformat(published[:10]) if published else None,
            deadline_at=_deadline(
                raw.get("deadline-receipt-tender-date-lot"),
                raw.get("deadline-receipt-tender-time-lot"),
            ),
            language=_LANG_A3_TO_A2.get(lang3 or ""),
            documents=_documents(pdf, raw.get("document-url-lot")),
            raw=raw,
        )

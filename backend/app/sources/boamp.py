"""BOAMP. Los datos abiertos de la DILA se publican con Licence Ouverte 2.0 (Etalab).

La ficha del dataset no declara licencia propia: vale la del sitio
(«sauf mention contraire»). La búsqueda no es de frase exacta.

Se piden avisos de licitación. `famille = JOUE` ya está en TED: no se ingiere
y se cuenta en `skipped_eu`.
"""

import json
from collections.abc import Iterable
from datetime import date, datetime

import httpx

from app.models.opportunity import Buyer, Document, NoticeKind, Opportunity, OpportunityType
from app.sources.base import SOURCE_SUBSECTORS, Source
from app.sources.terms import search_pairs
from app.vertical import Vertical

SEARCH_URL = "https://www.boamp.fr/api/explore/v2.1/catalog/datasets/boamp/records"
_KEEP = {"APPEL_OFFRE", "RECTIFICATIF", "PRE-INFORMATION", "PERIODIQUE"}
_PAGE = 100


def boamp_decision(raw: dict) -> str:
    """`keep`, `eu` (ya va a TED) o `skip` (adjudicación u otro aviso)."""
    if raw.get("famille") == "JOUE":
        return "eu"
    if raw.get("nature") not in _KEEP:
        return "skip"
    return "keep"


def notice_body(raw: dict) -> dict:
    """Texto largo y enlaces que viven en `donnees`, no en el título `objet`."""
    blob = raw.get("donnees")
    if isinstance(blob, str):
        try:
            blob = json.loads(blob)
        except json.JSONDecodeError:
            blob = None
    found: dict[str, str] = {}
    if isinstance(blob, dict):
        _read_notice(blob, found)
    return found


def pdf_url(raw: dict) -> str | None:
    """La ficha de BOAMP arma el PDF así: esquema 3 usa FILES/PDF/año/mes."""
    ident = str(raw.get("idweb") or "")
    published = str(raw.get("dateparution") or "")
    if not ident or len(published) < 7:
        return None
    year, month = published[:4], published[5:7]
    if str(raw.get("source_schema") or "").startswith("3"):
        return f"https://www.boamp.fr/telechargements/FILES/PDF/{year}/{month}/{ident}.pdf"
    filename = str(raw.get("filename") or ident)
    return f"https://www.boamp.fr/telechargements/PDF/{year}/{filename}/{ident}.pdf"


def _read_notice(node: dict, found: dict[str, str]) -> None:
    market = node.get("natureMarche")
    if isinstance(market, dict):
        text = market.get("description")
        if isinstance(text, str) and text.strip():
            found["description"] = " ".join(text.split())
    communication = node.get("communication")
    if isinstance(communication, dict):
        url = communication.get("urlDocConsul")
        if isinstance(url, str) and url.startswith("http"):
            found["consultation"] = url
    for value in node.values():
        if isinstance(value, dict):
            _read_notice(value, found)


def _documents(raw: dict, body: dict) -> list[Document]:
    documents = []
    pdf = pdf_url(raw)
    if pdf:
        documents.append(Document(url=pdf, name="Notice (PDF)", kind="notice", access="fetch"))
    consultation = body.get("consultation")
    if consultation:
        documents.append(
            Document(
                url=consultation, name="Consultation documents", kind="portal", access="link_only"
            )
        )
    return documents


def _where(since: date, term: str) -> str:
    safe = term.replace('"', " ").strip()
    natures = ", ".join(f'"{nature}"' for nature in sorted(_KEEP))
    return (
        f"dateparution >= date'{since.isoformat()}' "
        f"AND nature in ({natures}) "
        f'AND search(objet, "{safe}")'
    )


class BoampSource(Source):
    id = "boamp"
    kind = "api"
    volume_alert = False

    def fetch(self, since: date, vertical: Vertical) -> Iterable[dict]:
        pairs = search_pairs(vertical, self.id)
        if not pairs:
            raise ValueError(
                "BOAMP: el vertical no tiene search_terms.boamp; no se baja el archivo entero."
            )
        self.skipped_eu = 0
        seen: dict[str, dict] = {}
        with httpx.Client(timeout=40, headers={"User-Agent": "blue-tender/1.0"}) as client:
            for subsector, term in pairs:
                offset = 0
                while offset < 5000:
                    response = client.get(
                        SEARCH_URL,
                        params={"where": _where(since, term), "limit": _PAGE, "offset": offset},
                    )
                    response.raise_for_status()
                    payload = response.json()
                    rows = payload.get("results") or []
                    for row in rows:
                        decision = boamp_decision(row)
                        ident = str(row.get("idweb") or "")
                        if decision == "skip" or not ident:
                            continue
                        if ident in seen:
                            found = seen[ident].setdefault(SOURCE_SUBSECTORS, [])
                            if subsector not in found:
                                found.append(subsector)
                            continue
                        row = dict(row)
                        if decision == "eu":
                            row["_skip_eu"] = True
                        row[SOURCE_SUBSECTORS] = [subsector]
                        seen[ident] = row
                    total = int(payload.get("total_count") or 0)
                    offset += _PAGE
                    if not rows or offset >= total:
                        break
        yield from seen.values()

    def to_tender(self, raw: dict) -> Opportunity:
        ident = str(raw.get("idweb") or raw.get("filename") or "")
        title = raw.get("objet") or raw.get("nomacheteur")
        if not ident or not title:
            raise ValueError("anuncio BOAMP sin id o sin objeto")
        end = raw.get("datelimitereponse")
        deadline = None
        if end:
            try:
                deadline = datetime.fromisoformat(str(end))
            except ValueError:
                deadline = None
        published = str(raw.get("dateparution") or "")[:10]
        notice = NoticeKind.pin if raw.get("nature") == "PRE-INFORMATION" else None
        kind = (
            OpportunityType.prior_information_notice
            if raw.get("nature") == "PRE-INFORMATION"
            else OpportunityType.tender
        )
        buyer = raw.get("nomacheteur")
        folder = raw.get("contractfolderid")
        body = notice_body(raw)
        return Opportunity(
            id=Opportunity.make_id(self.id, ident),
            source_id=self.id,
            external_id=ident,
            url=raw.get("url_avis") or f"https://www.boamp.fr/avis/detail/{ident}",
            type=kind,
            notice=notice,
            title=str(title),
            description=body.get("description") or raw.get("objet"),
            documents=_documents(raw, body),
            buyer=Buyer(name=str(buyer), country="FR") if buyer else None,
            country="FR",
            language="fr",
            published_at=date.fromisoformat(published) if published else None,
            deadline_at=deadline,
            dedupe_key=str(folder) if folder else None,
            raw=raw,
        )

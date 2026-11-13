"""Similitud entre una oportunidad y un proyecto ya financiado.

Sin embeddings se reparte el peso del vector entre el solape de palabras.
Con embeddings (listas de la misma longitud) se usa el reparto de la v1:
0,45 vector, 0,20 subsector, 0,15 programa, 0,10 palabras, 0,10 recencia.

El historial exige además una evidencia (mismo topic, mismo CPV específico o texto
parecido). Sin ella la fila no entra: un volcado grande no debe rellenar la ficha
con las treinta menos malas.
"""

import math
import re
from collections import Counter
from datetime import date

_WORD = re.compile(r"[^\W_]{4,}", re.UNICODE)
# Palabras que aparecen en casi cualquier convocatoria y no dicen de qué va.
_STOP = {
    "project",
    "projects",
    "european",
    "development",
    "innovative",
    "technologies",
    "technology",
    "systems",
    "system",
    "solutions",
    "solution",
}


def _tokens(text: str) -> set[str]:
    return {match.group(0).lower() for match in _WORD.finditer(text or "")}


def _cosine(a: list[float] | None, b: list[float] | None) -> float | None:
    if not a or not b or len(a) != len(b):
        return None
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return None
    return dot / (na * nb)


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _project_text(project: dict) -> str:
    return " ".join(
        [project.get("title") or "", project.get("objective") or "", project.get("topic_title") or ""]
    )


def _topic_codes(project: dict) -> set[str]:
    value = project.get("topics")
    if isinstance(value, str):
        value = value.split(",")
    codes = {str(item).strip() for item in value or [] if str(item).strip()}
    topic = project.get("topic")
    if isinstance(topic, str) and topic.strip():
        codes.update(part.strip() for part in topic.split(",") if part.strip())
    return codes


def same_topic(opportunity, project: dict) -> bool:
    """Mismo topic de verdad: no una convocatoria en cascada, y con subsector en común."""
    topic = getattr(opportunity, "topic_id", None)
    external = str(getattr(opportunity, "external_id", "") or "")
    if not topic or external.startswith("cascade-"):
        return False
    if topic not in _topic_codes(project):
        return False
    return bool(set(opportunity.subsectors) & set(project.get("subsectors") or []))


def specific_cpv(codes, digits: int) -> set[str]:
    """Prefijos de CPV con al menos `digits` cifras distintas de cero.

    73000000 (investigación, genérico) no cuenta. 31321500 (cable submarino) sí.
    """
    found = set()
    for code in codes or []:
        text = str(code).strip()
        if len(text.rstrip("0")) >= digits:
            found.add(text[:digits])
    return found


def _shared(a: set[str], b: set[str]) -> set[str]:
    return {token for token in a & b if token not in _STOP}


def _idf_cosine(left: set[str], right: set[str], idf: dict[str, float], default: float) -> float:
    if not left or not right:
        return 0.0

    def weight(token: str) -> float:
        return idf.get(token, default)

    num = sum(weight(token) ** 2 for token in left & right)
    left_norm = math.sqrt(sum(weight(token) ** 2 for token in left))
    right_norm = math.sqrt(sum(weight(token) ** 2 for token in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return num / (left_norm * right_norm)


# Cuántas veces se trocea el texto de un proyecto. La ficha no debe sumar en la segunda llamada.
_PROJECT_TOKEN_CALLS = 0


def project_token_calls() -> int:
    return _PROJECT_TOKEN_CALLS


def reset_project_token_calls() -> None:
    global _PROJECT_TOKEN_CALLS
    _PROJECT_TOKEN_CALLS = 0


def _doc_key(row: dict):
    return row.get("project_id") or row.get("url") or (row.get("title"), row.get("acronym"))


def _project_tokens(row: dict) -> set[str]:
    global _PROJECT_TOKEN_CALLS
    _PROJECT_TOKEN_CALLS += 1
    return _tokens(_project_text(row))


class ProjectStats:
    """Palabras, pesos y norma de un proyecto. Se calculan una vez por volcado."""

    __slots__ = ("norm", "tokens", "weight_sq")

    def __init__(self, tokens: set[str], idf: dict[str, float], default: float):
        self.tokens = tokens
        self.weight_sq: dict[str, float] = {}
        total = 0.0
        for token in tokens:
            square = idf.get(token, default) ** 2
            self.weight_sq[token] = square
            total += square
        self.norm = math.sqrt(total) if total else 0.0


class PreparedCorpus:
    __slots__ = ("default", "idf", "projects")

    def __init__(self, idf: dict[str, float], default: float, projects: dict):
        self.idf = idf
        self.default = default
        self.projects = projects


def _idf_from_docs(docs: dict) -> tuple[dict[str, float], float]:
    counts = Counter(token for tokens in docs.values() for token in tokens)
    total = max(len(docs), 1)
    default = math.log((total + 1) / 1) + 1
    idf = {token: math.log((total + 1) / (count + 1)) + 1 for token, count in counts.items()}
    return idf, default


def _corpus(rows: list[dict]) -> tuple[dict[str, float], float]:
    docs: dict = {}
    for row in rows:
        docs.setdefault(_doc_key(row), _project_tokens(row))
    return _idf_from_docs(docs)


def prepare_corpus(rows: list[dict]) -> PreparedCorpus:
    """Trocea cada proyecto una vez y deja listos el IDF, la norma y las palabras."""
    docs: dict[object, set[str]] = {}
    for row in rows:
        docs.setdefault(_doc_key(row), _project_tokens(row))
    idf, default = _idf_from_docs(docs)
    projects = {key: ProjectStats(tokens, idf, default) for key, tokens in docs.items()}
    return PreparedCorpus(idf, default, projects)


def _cosine_prepared(opp_tokens: set[str], stats: ProjectStats, idf: dict[str, float], default: float) -> float:
    if not opp_tokens or not stats.tokens or stats.norm == 0:
        return 0.0
    numerator = 0.0
    opp_square = 0.0
    for token in opp_tokens:
        square = idf.get(token, default) ** 2
        opp_square += square
        hit = stats.weight_sq.get(token)
        if hit is not None:
            numerator += hit
    opp_norm = math.sqrt(opp_square) if opp_square else 0.0
    if opp_norm == 0:
        return 0.0
    return numerator / (opp_norm * stats.norm)


def score_project(
    opportunity,
    project: dict,
    today: date | None = None,
    idf: dict | None = None,
    idf_default: float = 1.0,
    opp_tokens: set[str] | None = None,
    proj_stats: ProjectStats | None = None,
) -> dict:
    today = today or date.today()
    opp_text = " ".join(
        [opportunity.title_en or opportunity.title, opportunity.summary_en or "", opportunity.description or ""]
    )
    if opp_tokens is None:
        opp_tokens = _tokens(opp_text)
    proj_tokens = proj_stats.tokens if proj_stats is not None else _project_tokens(project)
    lexical = _jaccard(opp_tokens, proj_tokens)
    if proj_stats is not None and idf is not None:
        text = _cosine_prepared(opp_tokens, proj_stats, idf, idf_default)
    elif idf is not None:
        text = _idf_cosine(opp_tokens, proj_tokens, idf, idf_default)
    else:
        text = lexical
    vector = _cosine(getattr(opportunity, "embedding", None), project.get("embedding"))
    sectors = _jaccard(set(opportunity.subsectors), set(project.get("subsectors") or []))
    same_programme = 1.0 if opportunity.programme_id and opportunity.programme_id == project.get("programme_id") else 0.0
    topic = 1.0 if same_topic(opportunity, project) else 0.0
    end = project.get("end_year")
    recency = 0.3
    if isinstance(end, int):
        age = max(0, today.year - end)
        recency = max(0.0, 1 - age / 10)
    words = text if idf is not None else lexical

    if vector is None:
        total = 0.55 * words + 0.20 * sectors + 0.15 * same_programme + 0.10 * recency
        parts = {
            "lexical": lexical,
            "text": text,
            "subsectors": sectors,
            "programme": same_programme,
            "same_topic": topic,
            "recency": recency,
            "shared_tokens": len(_shared(opp_tokens, proj_tokens)),
        }
    else:
        total = 0.45 * vector + 0.20 * sectors + 0.15 * same_programme + 0.10 * words + 0.10 * recency
        parts = {
            "embedding": vector,
            "subsectors": sectors,
            "programme": same_programme,
            "lexical": lexical,
            "text": text,
            "same_topic": topic,
            "recency": recency,
            "shared_tokens": len(_shared(opp_tokens, proj_tokens)),
        }
    return {"score": round(total, 4), "parts": parts}


def _evidence(opportunity, project: dict, parts: dict, cfg, kind: str) -> str | None:
    if kind == "awards":
        call_id = project.get("call_id")
        if call_id and call_id == opportunity.call_id:
            return None
        if not (set(opportunity.subsectors) & set(project.get("subsectors") or [])):
            return None
        if specific_cpv(opportunity.cpv, cfg.awards_min_cpv_digits) & specific_cpv(
            project.get("cpv"), cfg.awards_min_cpv_digits
        ):
            return "same_cpv"
        if parts["shared_tokens"] >= cfg.min_shared_tokens and parts["text"] >= cfg.awards_min_text_similarity:
            return "similar_text"
        return None
    if parts["same_topic"]:
        return "same_topic"
    if (
        parts["subsectors"] > 0
        and parts["shared_tokens"] >= cfg.min_shared_tokens
        and parts["text"] >= cfg.min_text_similarity
    ):
        return "similar_text"
    return None


def _opportunity_tokens(opportunity) -> set[str]:
    text = " ".join(
        [opportunity.title_en or opportunity.title, opportunity.summary_en or "", opportunity.description or ""]
    )
    return _tokens(text)


def rank_track_record(
    opportunity,
    participations: list[dict],
    *,
    cfg=None,
    kind: str = "cordis",
    limit: int | None = None,
    corpus: PreparedCorpus | None = None,
) -> tuple[list[dict], int]:
    """Organizaciones con evidencia, y cuántas había antes del límite."""
    seen = set()
    rows = []
    for row in participations:
        key = (
            row.get("pic") or row.get("org_name"),
            row.get("project_id") or row.get("url") or row.get("title"),
        )
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)
    if cfg is not None and corpus is None:
        corpus = prepare_corpus(rows)
    idf = corpus.idf if corpus is not None else None
    default = corpus.default if corpus is not None else 1.0
    opp_tokens = _opportunity_tokens(opportunity) if cfg is not None else None
    by_org: dict[str, dict] = {}
    for row in rows:
        stats = corpus.projects.get(_doc_key(row)) if corpus is not None else None
        scored = score_project(
            opportunity,
            row,
            idf=idf or None,
            idf_default=default,
            opp_tokens=opp_tokens,
            proj_stats=stats,
        )
        evidence = _evidence(opportunity, row, scored["parts"], cfg, kind) if cfg is not None else "listed"
        if evidence is None:
            continue
        key = row.get("pic") or row["org_name"]
        bucket = by_org.setdefault(
            key,
            {
                "org_name": row["org_name"],
                "country": row.get("country"),
                "activity_type": row.get("activity_type"),
                "pic": row.get("pic"),
                "sme": row.get("sme"),
                "demo": bool(row.get("demo")),
                "projects": [],
            },
        )
        bucket["projects"].append(
            {
                "id": row.get("project_id") or row.get("url") or row.get("acronym"),
                "acronym": row.get("acronym"),
                "title": row.get("title"),
                "url": row.get("url"),
                "role": row.get("role"),
                "programme_id": row.get("programme_id"),
                "end_year": row.get("end_year"),
                "buyer": row.get("buyer"),
                "amount_eur": row.get("amount_eur"),
                "score": scored["score"],
                "evidence": evidence,
            }
        )
    ranked = []
    for bucket in by_org.values():
        bucket["projects"].sort(key=lambda item: (item["evidence"] != "same_topic", -item["score"]))
        top = bucket["projects"][:3]
        bonus = 0.05 if any(project["role"] == "coordinator" for project in top) else 0
        bucket["score"] = round(sum(project["score"] for project in top) + bonus, 4)
        bucket["projects"] = top
        ranked.append(bucket)
    ranked.sort(
        key=lambda bucket: (
            not any(project["evidence"] == "same_topic" for project in bucket["projects"]),
            -min(len(bucket["projects"]), 3),
            -bucket["score"],
            bucket["org_name"] or "",
        )
    )
    cap = cfg.limit if cfg is not None and limit is None else (limit if limit is not None else 30)
    return ranked[:cap], len(ranked)


def rank_organisations(opportunity, participations: list[dict], limit: int = 30) -> list[dict]:
    """Ordena filas que ya existan, sin umbral. El historial usa `rank_track_record`."""
    ranked, _total = rank_track_record(opportunity, participations, cfg=None, limit=limit)
    return ranked

"""Presupuesto de contexto y coste de una respuesta.

Sonnet 5.5, por millón: 2 $ entrada, 10 $ salida, 2,50 $ escritura de caché
y 0,10 $ lectura. DeepSeek usa la tarifa punta publicada (la valle es la
mitad): Flash 0,30 / 1,20 $ y 0,006 $ el acierto de caché; V4 Pro 1,32 / 3,96 $
y 0,044 $. Una búsqueda web de DeepSeek cuenta 0,00075 $.
"""

BUDGET_TOKENS = 150_000
BUDGET_CHARS = BUDGET_TOKENS * 4

_INPUT = 2.0
_OUTPUT = 10.0
_CACHE_WRITE = 2.5
_CACHE_READ = 0.1


_SEARCH = 0.00075


def cost_usd(
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_write: int = 0,
    cache_read: int = 0,
    *,
    provider: str = "anthropic",
    model: str = "",
    searches: int = 0,
) -> float:
    prices = _prices(provider, model)
    total = (
        input_tokens * prices[0]
        + output_tokens * prices[1]
        + cache_write * prices[2]
        + cache_read * prices[3]
    )
    return round(total / 1_000_000 + searches * _SEARCH, 6)


def _prices(provider: str, model: str) -> tuple[float, float, float, float]:
    """Entrada, salida, escritura de caché y lectura, en dólares por millón."""
    if provider != "deepseek":
        return _INPUT, _OUTPUT, _CACHE_WRITE, _CACHE_READ
    name = model.lower()
    if "v4-pro" in name or name.startswith("claude-opus"):
        return 1.32, 3.96, 0.0, 0.044
    return 0.3, 1.2, 0.0, 0.006


def pack(documents: list[dict]) -> tuple[list[dict], list[dict]]:
    """Los que caben van enteros al modelo. El resto se consulta con search_documents."""
    attached, searchable, used = [], [], 0
    for doc in documents:
        size = sum(len(page.get("text") or "") for page in doc.get("pages") or [])
        if doc.get("bytes") and not size:
            size = BUDGET_CHARS  # un PDF escaneado cuenta como el tope: va solo si cabe él
        if used + size <= BUDGET_CHARS:
            attached.append(doc)
            used += size
        else:
            searchable.append(doc)
    return attached, searchable

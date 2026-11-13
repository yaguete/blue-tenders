# Backend

FastAPI + uv. Python ≥ 3.11. Ruff, línea 100.

## Arranque

```bash
uv sync
uv run pytest
uv run ruff check app tests
uv run uvicorn app.main:app --reload
uv run python -m app.jobs.ingest --source ted --days 1
uv run python -m app.jobs.cordis
uv run python -m app.jobs.ted_awards --days 365
uv run python -m app.jobs.seed_demo
```

## Módulos

| Ruta | Responsabilidad |
|---|---|
| `app/models/opportunity.py` | Modelo canónico. `app/models/tender.py` reexporta. |
| `app/sources/` | Un adaptador por fuente. `fetch` + `to_opportunity` (y `to_tender`, alias). |
| `app/pipeline/run.py` | ingest → prefilter → dedupe → enrich → index. |
| `app/enrich/` | Clasificar, extraer, analizar, traducir. |
| `app/quality/` | Validadores, citas, confianza, cola de revisión. |
| `app/search/` | Búsqueda con filtros inclusivos. |
| `app/partners/` | CORDIS (`cordis.py`), similitud (`score.py`) e historial de la ficha (`track_record.py`). |
| `app/matching/` | Encaje con el perfil, sin LLM. |
| `app/alerts/` | Búsquedas guardadas, recordatorios, baja. |
| `app/assistant/` | Panel: documentos por página, chat, herramientas y subidas de 24 h. Sin `DEEPSEEK_API_KEY` ni `ANTHROPIC_API_KEY`, no llama al modelo. |
| `app/store.py` | JSON local o Supabase. El historial va en `data/partners.json` o en `partner_*`, no en `load()`. |
| `supabase/migrations/` | Esquema. `0001` crea `tenders`; `0002` la renombra. `0003`–`0006` partners, cuenta, asistente e ingesta. `0007` el historial. |

## Contratos

- Fechas con zona horaria. Si la fuente no trae hora, inicio del día, nunca una hora inventada más tarde.
- Importes en EUR solo si la moneda ya es EUR o hay un tipo de cambio explícito. No convertir SEK a ojo.
- País en ISO 3166-1 alpha-2. Un código desconocido se deja vacío.
- `content_hash` cubre título, descripción, plazos e importes. Si hay ganadores o importe adjudicado, también. Si no cambia, enrich no llama al LLM.

## Eval

- `evals/gold/`: candidatos a etiquetar. `status: proposed` no es un gold label.
- `evals/assistant/questions.yaml`: preguntas del asistente. El workflow `eval-assistant` es manual.

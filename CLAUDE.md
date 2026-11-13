# blue-tender

Buscador de financiación y partners para la blue economy (v1: transición energética marina).
El motor es común; cada vertical es un YAML en `config/verticals/`.

## Mapa

| Carpeta | Qué es |
|---|---|
| `frontend/` | Next.js 15, App Router, Tailwind, shadcn/ui. Vercel. |
| `backend/` | FastAPI, uv. Fly.io (`fra`). |
| `config/` | Verticales, reglas de programa, financiadores, conocimiento, convocatorias curadas. |
| `docs/` | Esquema, fuentes, ADRs, producto, diseño, legal. |
| `.github/workflows/` | CI. La ingesta a mano sigue en `ingest.yml`; el horario está en Fly (`backend/crontab`). |

Regla: si un cambio toca `config/`, es de vertical o de catálogo. Si toca `backend/` o `frontend/`, es de producto. No hardcodear taxonomía, CPV ni reglas de cofinanciación en Python.

## Comandos

```bash
cd backend && uv sync && uv run pytest && uv run ruff check app tests
cd backend && uv run uvicorn app.main:app --reload
cd frontend && npm run dev
```

Sin `SUPABASE_URL`, la API lee y escribe `backend/data/opportunities.json`.

## Qué no romper

- `backend/tests/` cubre el adaptador de TED (anuncios reales) y el prefiltro. Un cambio de keywords o de CPV se justifica contra esos tests, no al revés.
- El prefiltro ahorra LLM: no descarta por `exclude_keywords` y no casa subcadenas.
- TED se consulta por CPV y por texto completo (`FT`). En `FT`, cada término lleva su propia cláusula (`FT ~ "a" OR FT ~ "b"`): `FT ~ ("a" OR "b")` devuelve 0 con un 200. No mandes `FT ~ (a AND b)` ni `NEAR`: casan con las palabras en cualquier parte del anuncio y traen ruido. Detalle en `backend/app/sources/ted.py`.
- Lo que TED encuentra por texto completo viaja en `raw["_source_subsectors"]`. El prefiltro lo deja pasar y el clasificador lo usa con confianza 0,4 si el título no nombra el sector.
- `Tender` es un alias de `Opportunity`. El campo `type` se mantiene; `kind` y `notice` se derivan de él.
- El historial de la ficha no sale de `load()`: CORDIS y las adjudicaciones de TED tienen su propia lectura, en el JSON local y en Supabase.

## Calidad de los datos

Un plazo o un requisito de elegibilidad inventado le cuesta una convocatoria al usuario.

- Nunca rellenar un plazo, un importe o una elegibilidad que la fuente no traiga.
- Cada dato derivado lleva un `Fact` (`origin`, `confidence`, y cita si viene de un texto).
- Orden de verdad: campo estructurado de la fuente, regla de programa, extracción con LLM, vacío.
- El LLM no pisa un plazo estructurado. Si chocan, el caso va a `review_queue`.
- Lo generado se marca `generated`. Lo copiado del documento, `extracted`.

## LLM

- Sin `ANTHROPIC_API_KEY`, el enrich usa reglas y no llama a la API.
- Clasificar, traducir y analizar la ficha: Haiku. El asistente usa `ASSISTANT_ANSWER_MODEL`; con `DEEPSEEK_API_KEY`, DeepSeek.
- No reprocesar una oportunidad si `content_hash` no ha cambiado.
- Descargar documentos solo con `ENRICH_DOCUMENTS=1`.

## Fuera de la v1

Pagos, redacción de propuestas, CRM, app móvil, mensajería entre organizaciones y verticales distintos de blue economy. El modelo de planes (`plans`, `subscriptions`) existe para no migrar datos después; no hay cobro.

## Documentos

- [docs/opportunity-schema.md](docs/opportunity-schema.md)
- [docs/sources.md](docs/sources.md)
- [docs/data-quality.md](docs/data-quality.md)
- [docs/assistant.md](docs/assistant.md)
- [docs/decisions/](docs/decisions/)

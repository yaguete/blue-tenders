# Plan v1 en el repo

El plan aprobado está en el historial de la conversación y, si se copió al clonar, en `docs/plans/`. Este archivo es el índice operativo: qué se construyó y dónde vive. No sustituye las ADR.

## Decisiones cerradas

- PLACSP y BDNS entran en la v1, no solo el portal europeo.
- Préstamos, equity y filantropía sin plazo: directorio (`config/funders`), no mezclados con las calls.
- Asistente limitado al corpus propio.
- Filtros inclusivos: un campo vacío no esconde la oportunidad.
- Partners: CORDIS en la v1. Keep.eu cuando haya clave. Kohesio no.
- Dirección visual provisional: Instrument.

## Dónde está cada fase

| Fase | Entregable |
|---|---|
| 0 | `CLAUDE.md`, `AGENTS.md`, ADR 0003–0007, `docs/sources.md`, `config/programmes`, `config/verticals`, `evals/gold` |
| Diseño | `docs/design/`, `/design-lab` |
| Validación | `docs/product/validation-*.md` (las sesiones, cuando se hagan, en `docs/product/sessions/`) |
| 1 | Migración `0002`, modelo `Opportunity`, adaptadores TED, EU F&T, PLACSP, curated, búsqueda, `/search`, ficha |
| 2 | `0003`, CORDIS, `/funders`, `/compare`, `/admin/review`, BDNS |
| 3 | `0004`, perfil, encaje, guardados, ICS, alertas, baja, borrado |
| 4 | `0005`, asistente, `evals/assistant/questions.yaml` |
| 5 | `fly.toml`, CI, runbook, páginas vigiladas, ficha con metadatos |

## Corte de la demo

`uv run python -m app.jobs.seed_demo` carga el fixture real de TED y las calls curadas verificadas. La búsqueda y la ficha funcionan sin Supabase.

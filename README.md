# blue-tender

Motor de búsqueda de licitaciones y convocatorias (tenders + grants) por **verticales**.
Primer vertical: **blue economy**, empezando por la transición energética marina.

## Idea

Los agregadores horizontales trocean los nichos transversales entre categorías y buscan por keywords,
con mucho ruido (p. ej. "vessel" = barco y también recipiente). Aquí cada vertical se define por
configuración (taxonomía, geografías, keywords, códigos CPV) y el motor es común.

## Estructura

```
frontend/            UI (búsqueda, detalle, alertas)
backend/             FastAPI (app/…)
  api/               endpoints: search, tender detail, perfiles, alertas
  sources/           un adaptador por fuente → Tender canónico
  pipeline/          ingest → normalize → dedupe → enrich (LLM) → index
  matching/          ranking contra perfil + alertas
  models/            esquema Tender canónico
  jobs/              ingesta programada
config/verticals/    un YAML por vertical (blue-economy.yaml, …)
docs/
  sources.md         inventario de fuentes
  tender-schema.md   campos del Tender canónico
  decisions/         ADRs cortos
```

Regla: si un cambio toca `config/`, es de vertical; si toca `backend/` o `frontend/`, es de producto.

## Estado

v1 en construcción. El plan operativo está en [docs/plan-v1.md](docs/plan-v1.md). Empieza por [CLAUDE.md](CLAUDE.md).

```bash
cd backend && uv run uvicorn app.main:app --reload
cd frontend && npm run dev
```

Sin Supabase, la búsqueda lee `backend/data/opportunities.json` (se crea al arrancar si no existe).

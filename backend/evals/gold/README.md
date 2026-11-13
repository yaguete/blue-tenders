# Conjunto de referencia

Un gold label lo pone una persona. Lo que genera el script es un candidato (`status: proposed`).

No hay 150 etiquetas revisadas. El pool se construye así:

```bash
cd backend
uv run python -m evals.gold.propose          # el fixture de TED, pocas filas
TED_LIVE=1 uv run python -m evals.gold.propose --limit 150
```

La segunda llamada pide una página a TED y propone `relevant` si el prefiltro se queda el anuncio. María tiene que cambiar `status` a `confirmed` o `rejected`. Hasta entonces la precisión del clasificador no se da por medida.

Columnas: `source_id`, `external_id`, `title`, `proposed_relevant`, `proposed_subsectors`, `status`, `reviewer`.

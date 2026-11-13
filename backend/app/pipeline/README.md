# pipeline

1. **ingest**: ejecuta los adaptadores
2. **normalize**: fechas, moneda, país (ISO), idioma
3. **dedupe**: misma convocatoria publicada en varias fuentes
4. **enrich**: LLM → clasificación en la taxonomía del vertical, resumen, assessment del pliego
5. **index**: búsqueda full-text + filtros (+ embeddings si hace falta)

# 0004 · Asistente con herramientas y contexto de la ficha

Fecha: 2026-11-11 · Estado: aceptada

La 0009 sustituye el modo de lectura (fragmentos recuperados) por el documento entero con citas nativas, y la página `/assistant` por el panel flotante. Siguen las citas, la negativa a prometer elegibilidad y el SSE desde FastAPI.

## Contexto

Había dos opciones: tool use de Claude sobre funciones propias, o RAG clásico con pgvector. La primera resuelve preguntas de catálogo ("¿qué cierra en marzo?"). La segunda resuelve preguntas sobre el PDF de una convocatoria.

## Decisión

Combinación, limitada a nuestro corpus. No hay un chat generalista abierto a la web.

- Modo oportunidad: el prompt lleva la ficha, el análisis y los fragmentos ya indexados. Una herramienta `search_documents` busca en esos documentos si hace falta.
- Modo general: herramientas `search_opportunities`, `get_opportunity`, `search_knowledge` y `list_funders`. El conocimiento es `config/knowledge/` más los documentos indexados.
- Cada afirmación cita una fuente. Si no hay respaldo, se dice. No se promete elegibilidad.
- Sin clave de API, el modo oportunidad responde solo con campos ya guardados (extractivo). No improvisa.

## Consecuencias

- El streaming es SSE desde FastAPI. El front no reemite el flujo por Vercel.
- Cuotas en `usage_counters` y un techo diario (`ASSISTANT_DAILY_LIMIT`, por defecto 30).

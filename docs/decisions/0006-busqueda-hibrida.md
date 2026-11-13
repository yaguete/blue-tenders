# 0006 · Búsqueda híbrida y filtros inclusivos

Fecha: 2026-11-11 · Estado: aceptada

## Decisión

- La implementación de referencia es `backend/app/search/query.py` (tests en `test_search.py`): solape de términos sobre título, resumen y descripción, más los filtros. Cuando la tabla viva sea Supabase, esa función es la que hay que pasar a SQL; no hay una segunda copia sin tests. Los embeddings se guardan en `document_chunks` para el asistente, no para reordenar la lista en la v1.
- Un filtro de un campo vacío no esconde la oportunidad. La respuesta dice cuántas no traen ese dato. El cliente puede pasar `exclude_unknown` para el comportamiento estricto.
- Los ODS no son un filtro: se deducen del subsector. El rol de coordinador o socio vive en el perfil y ordena partners, no convocatorias.
- TRL y cuenca van en "más filtros" e indican cobertura.

## Consecuencias

- Indexar un embedding es opcional. La búsqueda funciona sin él.
- La ordenación `fit` solo existe si llega un perfil.

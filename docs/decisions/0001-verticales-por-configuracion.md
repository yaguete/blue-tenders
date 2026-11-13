# 0001 · Verticales por configuración

Fecha: 2026-11-10 · Estado: aceptada

## Contexto
El primer vertical es blue economy, pero la intención es escalar a otros (bioeconomy, circular…).

## Decisión
El motor (fuentes, pipeline, matching, UI) es común. Cada vertical es un YAML en `config/verticals/`
con taxonomía, keywords, exclusiones, CPV y geografías. La taxonomía se toma de una fuente oficial
cuando exista (EU Blue Economy Report para blue economy).

## Consecuencias
- Añadir un vertical = añadir un YAML + las fuentes específicas que no estén ya.
- La clasificación por subsector la hace el pipeline (enrich), no el adaptador de fuente.

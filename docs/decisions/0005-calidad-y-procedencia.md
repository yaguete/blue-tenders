# 0005 · Calidad y procedencia

Fecha: 2026-11-11 · Estado: aceptada

## Decisión

- Cada valor derivado se guarda en `opportunity_facts` (y en `Opportunity.facts` en el modelo): origen, confianza, documento, página y cita.
- Las columnas de `opportunities` guardan el valor resuelto. La tabla de facts explica de dónde sale.
- Una cita tiene que aparecer en el texto del documento (similitud ≥ 0,9). Si no aparece, el fact no se publica como extraído.
- Los campos críticos (plazo, tipos de entidad, consorcio, cofinanciación) se extraen dos veces cuando hay LLM. Si no coinciden, van a revisión.
- Durante las dos primeras semanas de datos reales, el 100 % de los campos críticos de lo que se enseñe pasa por revisión humana. Después, una muestra del 10 % más todo lo de confianza baja.

## Consecuencias

- La ficha muestra "extracted" o "generated", la fecha de actualización y un enlace a la convocatoria oficial.
- Un reporte de usuario crea una fila en `user_reports` y en `review_queue`.

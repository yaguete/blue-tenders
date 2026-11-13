# Calidad de los datos

## Orden de verdad

1. Campo estructurado de la fuente (fecha de TED, importe de BDNS).
2. Regla de programa en `config/programmes/` (una RIA de Horizon Europe exige consorcio).
3. Extracción con LLM, con cita literal.
4. Vacío.

Un paso posterior no pisa un plazo del paso anterior. Si el texto y el campo estructurado dicen cosas distintas, el caso entra en `review_queue` con motivo `conflict`.

El resumen (`summary_en` y el bloque Summary) describe la oportunidad, no el texto de origen. No dice que el texto es corto ni qué datos faltan. Si la fuente no da para más que el título, o es una frase de relleno (`config/knowledge/boilerplate.yaml`), no hay resumen. `app.jobs.fix_summaries` rehace los que ya se guardaron así, sin tocar el hash.

## Validadores

En `backend/app/quality/validate.py`:

- La apertura es anterior al cierre.
- La cofinanciación está entre 0 y 100.
- El TRL está entre 1 y 9.
- El importe por proyecto no supera el presupuesto total.
- El país, si viene, está en la lista ISO que ya usa el adaptador.
- La cita de un fact aparece en el texto del documento (similitud ≥ 0,9). Si no, el fact no se considera extraído.

## Confianza

- `source`: 0,95.
- `programme_rule`: 0,7. Las bases específicas de una call pueden excepcionar el anexo general.
- `llm` con cita verificada: 0,6, o 0,85 si una segunda extracción coincide.
- `llm` sin cita verificada: no se publica el valor; se encola.
- `manual`: 0,9 hasta que alguien lo revise otra vez; la ficha enseña la fecha.

Por debajo de 0,75 en un campo crítico, la interfaz muestra "Verify in the official call".

## Revisión

Cola en la tabla `review_queue` y en `GET /admin/review` (cabecera `X-Admin-Token`, el mismo valor que `ADMIN_TOKEN`).

Motivos: `low_confidence`, `conflict`, `sample`, `user_report`.

Objetivo, medido por fuente cuando haya muestra revisada: ≥ 98 % de plazos correctos y ≥ 95 % de elegibilidad correcta. Hoy el conjunto gold está en `proposed`; esos porcentajes no se dan por cumplidos.

## Frescura

La ingesta diaria vuelve a leer las oportunidades abiertas. Si cambia el hash, se guarda el valor anterior en `field_history` y las alertas pueden avisar.

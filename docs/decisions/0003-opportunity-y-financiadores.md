# 0003 · Opportunity y perfiles de financiador

Fecha: 2026-11-11 · Estado: aceptada

## Contexto

El modelo `Tender` solo cubría licitaciones, subvenciones, anuncios previos y adjudicaciones. La v1 también tiene premios, asistencia técnica, préstamos, equity y financiación combinada. Muchos préstamos y fondos no se publican con plazo.

## Decisión

- La entidad canónica pasa a ser `Opportunity`. `Tender` queda como alias. La tabla `tenders` se renombra a `opportunities` en la migración `0002`. Una vista `tenders` conserva las filas con `kind = 'tender'` que no son adjudicaciones.
- `type` se mantiene por compatibilidad con el adaptador de TED y los tests. `kind` y `notice` se derivan de él cuando no vienen informados.
- `blended` no es un cajón: `instruments` guarda la mezcla (por ejemplo, subvención más equity).
- Lo que no tiene convocatoria con plazo es un perfil en `funders` (`is_directory_listed`) cargado desde `config/funders/`. Si hay un proceso de solicitud continuo, además existe una oportunidad con `deadline_model = continuous`.

## Consecuencias

- La API nueva es `/opportunities`. `/tenders` responde 308 hacia ella.
- Añadir un tipo de financiación no exige una tabla nueva.

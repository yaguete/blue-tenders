# 0011 · Consorcios que acaban

Fecha: 2026-11-13 · Estado: aceptada

## Contexto

El historial de la ficha responde quién ha hecho algo parecido. Quien arma un consorcio pregunta otra cosa: quién termina en los próximos meses, y quién se está llevando los contratos de este corte. No es una bandeja para escribirles. La v1 no tiene mensajería: es una lista para que la fundación decida a quién llama.

## Decisión

- En una subvención, la ficha lista los consorcios del mismo subsector cuya fecha de fin cae en los próximos `ending_window_months` (9 en el YAML). La fecha es la del registro. Sin fecha no se estima, y un año suelto no cuenta. Cada proyecto es un consorcio, con sus socios; no hay tope de 30.
- La lista se guarda con el historial, por proyecto y con un trimestre de margen. La ficha recorta la ventana al abrirse. Un socio se marca relevante si además sale en el historial de esa convocatoria.
- Search filtra por ese cruce (`wrapping_up`), no por «el subsector tiene proyectos que acaban»: eso daría el mismo número a todas las convocatorias del subsector. La tarjeta enseña el recuento.
- El parecido de texto sigue siendo el del historial, y solo con CORDIS. La ventana no mide parecido: entra por subsector, también si la ficha no está en inglés.
- LIFE no entra en esta ronda. La base pública no ofrece un volcado con términos de reutilización claros (spike del 13 nov). Keep.eu sigue esperando la clave. Si alguno llega al almacén de proyectos, la ventana lo lee igual.
- En una licitación, el historial de adjudicaciones enseña el importe adjudicado frente al presupuesto base de la licitación del mismo expediente, y el fin de contrato cuando la fuente lo trae. PLACSP aporta adjudicatario, importe y fin desde el feed diario. No hay carga hacia atrás: solo entra lo que pase el CPV y el prefiltro a partir de ahora. TED usa `contract-duration-end-date-lot`; si los lotes no coinciden, el campo se queda vacío.

## Consecuencias

- Una página vigilada de un programa de subvenciones declara `kind: grant`. Sigue siendo información previa, y el historial que le corresponde es el de CORDIS, no el de adjudicaciones de TED.
- No hay página nueva. El fin de contrato viaja como fact `contract_end_at` en la oportunidad.
- Los candidatos de la ventana se guardan con el historial (`0013_ending_soon.sql`, columna `ending`, aplicada el 13 nov 2026) con un trimestre de margen: la ficha recorta la ventana al abrirse y no tira del volcado en cada petición. Sin registro válido, se calcula en vivo y queda pendiente.
- El espejo normalizado (`opportunity_partner_matches`) solo lleva organizaciones CORDIS: un adjudicatario de TED o PLACSP no está en `partner_orgs` y viaja solo en el registro.
- El historial de una subvención también se enseña por proyecto parecido, con todos sus socios (`0014_track_record_projects.sql`). Agrupado por organización repetía el mismo proyecto en cada línea: en los datos del 14 nov, 30 organizaciones salían de 1 a 8 proyectos. El tope de `track_record.limit` pasa a contar proyectos; cortar por organizaciones dejaba consorcios a medias (VIGIMARE con 4 de 19 socios). Cada socio dice en qué otros proyectos parecidos está, que era lo que destacaba la lista por organización. Relevante, para «quién acaba», es cualquier socio de esos proyectos. Las adjudicaciones de TED y PLACSP se agrupan igual, por adjudicación: 27 de 130 tienen varios adjudicatarios (acuerdos marco, hasta 27) y reúnen el 57 % de las filas. Por organización, el importe de la adjudicación se repetía en cada ganador y parecía suyo. Ahí los adjudicatarios se ven sin clic.

# Inventario de fuentes

Actualizado el 11 nov 2026. Estados: `por probar` → `parseable` → `adaptador hecho` → `en producción` / `descartada`.

Los spikes están en `backend/spikes/` y las notas de la pasada en [spikes/2026-11-11.md](spikes/2026-11-11.md). "Adaptador hecho" significa que hay código y tests con fixture; no que el cron lleve meses estable.

| id | nombre | acceso | licencia y términos | volumen esperado | filtros que aporta | huecos | estado |
|---|---|---|---|---|---|---|---|
| ted | TED API v3 `POST /v3/notices/search` | API anónima. `fields` sin comodín. `IN` separado por espacios. Máximo 250 por página, paginación ITERATION. | Reutilización de documentos de la Comisión. Atribución. | ~10–40 anuncios del sector por semana tras CPV y prefiltro. Miles al día sin filtro. | Tipo licitación, país, NUTS, CPV, comprador, valor estimado, plazo, PIN, adjudicación. El ganador sale de `winner-name`, `winner-country`, `winner-identifier` y `winner-size`. El importe adjudicado, de `result-value-notice` solo si la moneda es EUR y el valor es mayor que cero (`0` y `-1` se dejan vacíos). `award-value-eur` no existe en la API. | Cofinanciación y consorcio no aplican. Los pliegos suelen estar fuera de TED. Si las listas de ganador no miden lo mismo, se guarda el nombre y no se empareja el identificador. | adaptador hecho |
| eu-ft | EU Funding & Tenders, Search API `api.tech.ec.europa.eu/search-api/prod/rest/search?apiKey=SEDIA` | POST multipart. Cada parte con `Content-Type: application/json`. `text=***` es el comodín. Tipos 1, 2 y 8. El tipo 2 es subvención, no licitación. El tipo 8 es cascada, con clave `cascade-<callccm2Id>`. | Reutilización (Decisión 2011/833/UE) con atribución. La clave `SEDIA` es la pública del portal. | 30–120 temas abiertos o próximos relevantes, a confirmar en cada ingesta. | Programa, plazos (una fase, dos fases o varios cortes), presupuesto del topic, tipo de acción, proyectos esperados. | El detalle JSON solo se pide si falta la descripción. Los topics cerrados van en un job aparte (`listed=false`) y no salen en la búsqueda de abiertas. | adaptador hecho, en el cron |
| placsp | Plataforma de Contratación del Sector Público, feed ATOM CODICE | `sindicacion_643`. Se sigue `rel="next"` hasta pasar la marca de agua. | Ley 37/2007: atribución, sin alterar el sentido. | 5–20 a la semana tras CPV, keywords y lista de compradores. | Igual que TED más enlaces a pliegos. El plazo sale de `TenderSubmissionDeadlinePeriod` cuando existe. | Español. Una entrada sin CPV se conserva. | adaptador hecho, en el cron |
| placsp-regional | Mismo CODICE, feed autonómico `sindicacion_1044` | Su propia marca de agua. | Igual que PLACSP. | Lo que no esté en el feed estatal. | Los mismos campos. | No se añade `sindicacion_1143` (contratos menores). | adaptador hecho, en el cron |
| bdns | BDNS / SNPSAP `infosubvenciones.es/bdnstrans/api` | Búsqueda por `descripcion` y `fechaDesde`. El detalle (`numConv`) trae el plazo, el importe y los beneficiarios. La hora solo se lee de `textFin` si trae `HH:MM`. | Datos abiertos. No ingerir concesiones a personas físicas. Si el filtro no reduce el total, la petición se aborta: el API ignora parámetros desconocidos y devolvería el archivo entero. | Alto en bruto; poco tras el prefiltro del vertical. | Tipo de beneficiario, instrumento, importe, órgano, fondo. | Una frase ("un mes desde la publicación") no se convierte en fecha. | adaptador hecho, en el cron |
| curated | `config/curated/calls.yaml` | Archivo revisado en git. | Cada ficha cita su URL oficial. | Las que alguien verifique a mano. | Lo que la ficha traiga, con `origin: manual`. | No escala. Sirve para la demo y para las fuentes de María hasta tener adaptador. | adaptador hecho |
| cinea | Calls for tenders de CINEA | HTML. | Reutilización institucional. | Bajo. | Duplica TED y el portal. | | por probar. Spike de 1 h antes de escribir adaptador. Si duplica, se descarta. |
| mercator | Mercator Ocean | HTML. | Por confirmar en la página. | Muy bajo y fuera del corte energético. | | | en cola de páginas vigiladas |
| cordis | CORDIS H2020 y Horizon Europe. Zips CSV en `https://cordis.europa.eu/data/cordis-h2020projects-csv.zip` y `cordis-HORIZONprojects-csv.zip` (data.europa.eu; `last-modified` 10 nov 2026). | CSV separado por `;`: `project.csv`, `organization.csv`, `topics.csv`. Job propio `app.jobs.cordis`, días 1 y 15 a las 04:30. No entra en `REGISTRY` ni en `ingest_runs`. | Reutilización de la Comisión. Sin contactos, dirección, NIF ni geolocalización (ADR 0007). `UK`→`GB`, `EL`→`GR`. | Volcado entero: 35.389 + 24.419 proyectos. Tras el corte del vertical (`keywords` + `project_keywords`), medido el 11 nov 2026: 873 proyectos, 7.035 participaciones y 3.740 organizaciones, antes de quitar bajas (`endOfParticipation`) y proyectos `TERMINATED`. | PIC, país, tipo de actividad, pyme, rol, acrónimo, título, objetivo, topic, programa, año de fin, URL del proyecto. | No es una fuente de convocatorias abiertas. Una fila duplicada `(PIC, proyecto)` se queda con el rol principal. | adaptador hecho, en el cron |
| keep-eu | Keep.eu, Interreg | API con clave que concede Interact (`keep.support@interact.eu`). Atribución obligatoria. | Términos de keep.eu. Acceso caso a caso. | Proyectos de cooperación territorial, muy relevantes para fundaciones. | Cuenca, socios, programa. | La clave no está pedida todavía: borrador en [outreach/keep-eu-request.md](outreach/keep-eu-request.md). | por probar |
| kohesio | Beneficiarios de cohesión | CSV por país en kohesio.ec.europa.eu. | Datos de las autoridades de gestión. La Comisión no garantiza la exactitud. | Ruidoso (FEDER, FSE, FC). | Socios de obra pública, no de I+D. | Nombres sin identificador estable. | spike, no en la v1 de partners |
| watched | Páginas vigiladas (`config/watched.yaml`) | HTML. Se compara el texto visible (`selector`), no los bytes. Un cambio deja un borrador con una cita. | La de cada sitio. | Mercator y CINEA. El resto de la cola (CETPartnership, cascade de la Misión, Fundo Azul, ADEME) sigue pendiente: no se inventa la URL. | Lo que el revisor confirme. | El job semanal no publica solo. | adaptador hecho, fuera de la ingesta diaria |
| fts | Find a Tender (Reino Unido), API OCDS | `find-tender.service.gov.uk/api/1.0/ocdsReleasePackages`. | Open Government Licence. | Por medir en 90 días antes de ponerlo en el cron. | Título, descripción, valor, plazo si el release lo trae. | Si el volumen del sector es bajo, no se programa. | adaptador hecho, fuera del cron |
| boe | Sumario del BOE | JSON `datosabiertos/api/boe/sumario/{fecha}`. | Datos abiertos del BOE. | Señal temprana del día. | Disposición que nombra el sector. Entra como información previa, sin plazo inventado. | Cuando la convocatoria exista, el enlace bueno es el de BDNS. | adaptador hecho, fuera del cron |
| boamp | BOAMP | API Explore `datasets/boamp/records`. La búsqueda no es de frase exacta. | Los datos abiertos de la DILA se publican con Licence Ouverte 2.0. Confirmar esa licencia en la ficha de este dataset antes de programarlo. | Por medir. | Objeto, comprador, plazo si el registro lo trae. | Fuera del cron hasta esa confirmación. | adaptador hecho, fuera del cron |

## Documento que lee el asistente

| Fuente | Qué se adjunta | Qué no se lee |
|---|---|---|
| eu-ft | Texto del topic, por secciones (`##`). En Horizon, los anexos generales una sola vez (`config/knowledge/horizon-annexes.yaml`). | La guía del programa, la decisión de suma global y el enlace de partner search (solo enlace). |
| ted | PDF del anuncio (`links.pdf`). | Pliegos: `document-url-lot` es un enlace. Muchas plataformas piden registro. |
| placsp | Pliegos administrativos y técnicos que ya vienen en la entrada, más el anuncio. | Un pliego que no esté en el feed. |
| bdns | PDF de `documentos` y bases de `urlBasesReguladoras`, si el detalle los trae. | |
| curated | El `url` cuando ya es un PDF (SBEP). | |
| boe, boamp, fts | | Fuera de la v1. Solo el enlace al anuncio. |

## Revisión trimestral

La carga histórica de adjudicaciones de TED (`uv run python -m app.jobs.ted_awards --days 365`) no es una fuente de convocatorias: busca solo por texto completo, con los tipos `can-standard`, `can-social`, `can-desg`, `can-tran` y `can-modif`, y no escribe en `ingest_runs`. Medido el 11 nov 2026, 365 días por CPV eran 11.361 avisos; por el texto del vertical, 175 avisos (133 con ganador). El umbral para enseñarlos está en `track_record` del YAML.

Cada trimestre: volumen de Find a Tender en 90 días, ficha de licencia de BOAMP, y si las keywords del Mar del Norte (`walstroom`, `landstrøm`, `landström`, `søkabel`, `windpark op zee`, `havvind`) siguen siendo las que usa el sector. Están en el YAML con ese pendiente.

## Directorio de financiadores

`config/funders/*.yaml`. No son convocatorias. Perfiles con instrumento, geografía y enlace a la fuente primaria. Si el ticket no está verificado, el campo va vacío: no se rellena de memoria.

## Filtros y de dónde sale el dato en la v1

| Filtro | Fuente estructurada | Si no está |
|---|---|---|
| Tipo de financiación | TED, portal, BDNS (`instrumentos`), curated | No se muestra el valor. |
| Estado y plazo | TED, portal, PLACSP | BDNS en texto: no se publica la fecha sin revisión. |
| Subsector | Ninguna lo da cerrado | Clasificador (reglas y, con clave, Haiku). |
| Tipo de financiador | Catálogo `funders` y órgano de BDNS | Vacío, y el filtro inclusivo la conserva. |
| Programa | Portal (framework programme), reglas | Vacío. |
| País elegible | BDNS, anexos del portal vía reglas | "Abierta a toda la UE" si la regla del programa lo dice. Si no se sabe, vacío. |
| Tipo de entidad | BDNS `tiposBeneficiarios` | Regla de programa o extracción citada. |
| Consorcio | Casi nunca estructurado | Regla (RIA, IA, CSA) con confianza 0,7. |
| Importe | Portal, TED, BDNS, PLACSP | Vacío. No se estima. |
| Cofinanciación | A veces en el portal | Regla del tipo de acción. |
| Misión Océano | Topic `HORIZON-MISS-*-OCEAN` | Etiqueta manual en curated. |
| Cuenca | Programa (Interreg MED) o NUTS costero (`config/geographies/sea-basins.yaml`, incompleto) | Vacío. Filtro secundario. |
| TRL | Casi nunca | Extracción citada o vacío. El rango "aproximado" por tipo de acción no se guarda como si fuera un dato de la call. |
| ODS | No | Dedicado del subsector. No es filtro. |

## Hueco de María Pérez

`config/watched.yaml` y filas nuevas en esta tabla. Hasta que lleguen, no se prometen en la interfaz.

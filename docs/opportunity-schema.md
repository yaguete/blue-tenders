# Opportunity canónico

Sustituye a [tender-schema.md](tender-schema.md). El modelo vive en `backend/app/models/opportunity.py`. `Tender` es un alias.

## Identidad

| Campo | Notas |
|---|---|
| `id` | SHA1 de `source_id:external_id`, 16 hex. |
| `source_id` | Fila de `docs/sources.md`. |
| `external_id` | Id en la fuente. |
| `url` | Anuncio oficial. |
| `content_hash` | Título, descripción, plazos e importes. Si hay `call_title`, también. Si no cambia, no se reextrae. |

## Tipo

| Campo | Valores |
|---|---|
| `type` | Legado: `tender`, `grant`, `prior_information_notice`, `award`. |
| `kind` | `grant`, `tender`, `loan`, `equity`, `prize`, `technical_assistance`, `blended`. |
| `notice` | `contract_notice`, `pin`, `award_notice`, `call_for_proposals`, `cascade`, `continuous`. |
| `instruments` | Lista, para mezclas. Un EIC Accelerator puede ser `["grant", "equity"]` con `kind = blended`. |

Derivación por defecto: `tender` → kind tender + contract_notice; `grant` → grant + call_for_proposals; `prior_information_notice` → tender + pin; `award` → tender + award_notice. Las adjudicaciones no salen en la búsqueda.

## Financiador y programa

`funder_id`, `programme_id`, `call_id`, `topic_id`, `type_of_action`, `mission_ocean`. El comprador de una licitación sigue en `buyer` (nombre, país, tipo).

`call_id` no significa lo mismo en cada fuente. En el portal es el identificador de la call (`HORIZON-CL5-2023-D3-02`), el paquete que agrupa varios topics. En TED y en PLACSP es el procedimiento. La ficha se guarda por topic, no por call.

Facts que salen del portal, todos con `origin: source`:

| Fact | Qué es |
|---|---|
| `call_title` | Nombre de la call. Entra en `content_hash` para que una ficha ya guardada se vuelva a leer. |
| `call_topics_count` | Topics distintos en `budgetTopicActionMap`. |
| `proposals_submitted` | Propuestas presentadas a este topic, leídas de `latestInfos`. Lleva la línea como `quote`. Si dos líneas dan números distintos, no se guarda. |
| `expected_grants` | Proyectos previstos, del mapa de presupuesto del topic. |

## Plazos y dinero

`opens_at`, `deadline_at` (el próximo o el único), `deadline_model` (`single`, `two_stage`, `multiple_cutoff`, `continuous`), `deadlines` (fase, fecha, zona), `status` (`open`, `forthcoming`, `closed`).

`budget_total_eur`, `amount_min_eur`, `amount_max_eur`, `cofunding_min`, `cofunding_max`. `budget` conserva importe y moneda originales. No se inventa el contravalor.

## Elegibilidad y tema

`eligible_entity_types`, `eligible_countries` (ISO o grupos: `EU27`, `HE_ASSOCIATED`), `consortium_required`, `consortium_min_partners`, `consortium_min_countries`.

`subsectors`, `relevance`, `sea_basins`, `trl_min`, `trl_max`, `sdgs` (deducidos, no filtrables), `cpv`, `nuts`.

## Texto

`title` y `description` en el idioma original. `title_en` y `summary_en` traducidos. `language` en ISO 639-1.

`documents[]`: `url`, `name`, `kind`, `access`. `access` es `fetch` (se descarga al abrir el chat), `inline` (el texto ya está en la ficha; el topic europeo) o `link_only` (se enseña el enlace y no se lee). El texto por página no va en la fila: va en `document_pages`.

## Procedencia

`facts[]`: `field`, `value`, `origin` (`source`, `programme_rule`, `llm`, `manual`, `scraped`), `confidence` (0–1), `document_id`, `page`, `quote`, `model`. `contract_end_at` es la fecha de fin de contrato cuando la fuente la trae (TED o PLACSP) y entra en `content_hash`. `award_value_eur` y `winners` también.

`analysis`: secciones con `text`, `origin` (`extracted` o `generated`) y `citations` (documento, página, cita). `analysis_updated_at`.

## Qué no va en la fila

Partners, perfiles y conversaciones son tablas aparte. Ver migraciones `0003`–`0005`. `ending_soon` de la ficha sale de `opportunity_track_record.ending`: consorcios (`consortia[]`, cada uno con `partners[]`) del mismo subsector que acaban en la ventana, más `total`, `consortia_total` y `relevant_total`. La lista guardada lleva un trimestre de margen y la lectura recorta a hoy. `track_record` de una subvención lleva `projects[]`: proyectos parecidos de CORDIS ordenados por parecido, cada uno con todos sus socios (`partners[]`, con `also`: otros proyectos parecidos donde está ese socio) y `projects_total`. El tope (`track_record.limit`) cuenta proyectos. En una licitación, `projects[]` son adjudicaciones parecidas, con comprador, importe, presupuesto base y fin de contrato una vez por adjudicación, y los adjudicatarios en `partners[]`. `items` sigue por organización para el espejo normalizado. La tarjeta de búsqueda añade `wrapping_up` (organizaciones del historial relevante que acaban en la ventana) solo si es mayor que cero.

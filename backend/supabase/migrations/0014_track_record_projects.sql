-- El historial de una subvención se enseña por proyecto parecido, con todos sus socios.
-- `items` sigue por organización: lo usa el espejo normalizado (opportunity_partner_matches).
-- `projects_total` cuenta los proyectos parecidos antes del tope.

alter table opportunity_track_record add column if not exists projects jsonb;
alter table opportunity_track_record add column if not exists projects_total int;

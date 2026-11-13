-- La lista de «quién acaba» viaja con el historial precalculado.
-- Se guarda con un trimestre de margen y la ficha recorta la ventana al abrirse;
-- así la lectura no tira del volcado de CORDIS en cada petición.

alter table opportunity_track_record add column if not exists ending jsonb;

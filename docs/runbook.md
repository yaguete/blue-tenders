# Runbook

## Local

```bash
cd backend && uv sync && uv run uvicorn app.main:app --reload
cd frontend && npm run dev
```

Si `backend/data/opportunities.json` no existe, el API carga el fixture de TED que pasa el prefiltro y la call curada de SBEP. Para regenerarlo: borrar ese archivo y reiniciar, o `uv run python -m app.jobs.seed_demo`.

El historial de organizaciones no va en ese JSON. En local: `uv run python -m app.jobs.cordis` y `uv run python -m app.jobs.ted_awards --days 365`. Escriben `backend/data/partners.json` y, las adjudicaciones, el mismo `opportunities.json`. En producción las migraciones se aplican a mano, en orden. `0013_ending_soon.sql` (la columna `ending` del historial) ya está aplicada: se aplicó el 13 nov 2026. Si cambias `track_record` en el YAML del vertical, recalcula con `uv run python -m app.jobs.track_record --all`; si no, cada ficha abierta se calcula en vivo al abrirla. El cron diario (`app.jobs.track_record`, sin `--all`) procesa los pendientes. Tras desplegar un cambio de la forma de `ending`, hay que lanzar `--all` a mano: si no, cada ficha tira del volcado de CORDIS. El frontend que lee `consortia` se despliega antes que ese backend.

`ALLOW_DEMO_AUTH=1` deja usar la cabecera `X-Demo-User` sin Supabase. No lo actives en un servidor público.

## Producción prevista

- Supabase Pro en `eu-central-1`. Aplicar `backend/supabase/migrations/` en orden.
- Fly en `fra`. Dos procesos: `app` (el API) y `cron` (Supercronic). Tras el primer deploy: `fly scale count app=1 cron=1`. El proxy solo habla con `app`. No despliegues a las horas del crontab: el deploy reinicia el cron.
- Vercel, funciones en `fra1`. `NEXT_PUBLIC_API_URL` apunta al API.
- Secretos, en Fly y no en el repositorio: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `ANTHROPIC_API_KEY`, `RESEND_API_KEY`, `ADMIN_TOKEN`. Opcionales: `OPS_EMAIL` (aviso si un job falla o el volumen cae) y `HEARTBEAT_URL` (latido al terminar bien).

## Si una fuente devuelve cero

El reloj está en Fly (`backend/crontab`), una fuente por ejecución. Si una falla, las demás siguen a su hora. La marca de agua no avanza en un fallo, así que el día siguiente relee el hueco con dos días de solape. `/health` enseña la última ejecución de cada fuente. `ingest.yml` ya no tiene horario: solo se lanza a mano.

## Copias

Supabase tiene las copias del plan de pago. El JSON local es solo la demo. El asistente descarga un documento al abrir el chat y guarda el texto por página (`document_files`, `document_pages`), no el PDF. `ENRICH_DOCUMENTS=1` sigue siendo la vía de lote y hoy no persiste ese texto.

## Borrado de una cuenta

`DELETE /me` con el JWT, o con `X-Demo-User` si la demo está permitida. Quita perfil, guardados, alertas y conversaciones de ese id.

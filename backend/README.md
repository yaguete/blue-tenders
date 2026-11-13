# backend

FastAPI (Python ≥3.11, gestionado con uv). Se despliega en Fly.io. La ingesta programada corre en el proceso `cron` de la misma imagen (Supercronic, `crontab`). GitHub Actions solo la lanza a mano.

Flujo: `app/sources/` → `app/pipeline/` → Supabase → `app/api/` ← `app/matching/`.
Todo lo que entra se convierte al `Tender` canónico (`app/models/tender.py`) antes de tocar el resto.

## Arranque

```bash
cd backend
uv sync
cp .env.example .env
uv run pytest
uv run uvicorn app.main:app --reload       # http://localhost:8000/docs
uv run python -m app.jobs.ingest --source ted --days 1
```

Base de datos: `supabase/migrations/` (aplicar con `supabase db push` desde `backend/`).
El Dockerfile se construye desde la raíz del repo (necesita `config/`):
`docker build -f backend/Dockerfile .`

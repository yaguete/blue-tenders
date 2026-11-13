# 0002 · Stack

Fecha: 2026-11-10 · Estado: aceptada

## Decisión
Mismo stack que WanderPlanner, para no pagar curva de aprendizaje:

| Pieza | Elección |
|---|---|
| Frontend | Next.js App Router + Tailwind + shadcn/ui, en Vercel |
| Backend | FastAPI (Python, uv), en Fly.io |
| Base de datos | Supabase Postgres (+ Auth para perfiles/alertas) |
| Búsqueda | Postgres full-text + pgvector |
| Enrich | Claude API |
| Jobs | Supercronic en un proceso `cron` de Fly (`backend/crontab`, hora de Madrid). GitHub Actions queda para CI y para lanzar la ingesta a mano |
| Email | Resend |

## Por qué Python en backend
Scraping, parseo de PDFs de pliegos y pipeline LLM son más cómodos en Python.

## Riesgos
- TED publica miles de anuncios/día: filtrar por CPV y keywords al ingestar.
- `raw` guarda JSON, no PDFs (PDFs como URL o en Storage).
- Supabase Free pausa tras una semana sin actividad.

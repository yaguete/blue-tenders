# 0007 · Regiones y RGPD

Fecha: 2026-11-11 · Estado: aceptada

## Decisión

- Supabase en `eu-central-1`, Fly en `fra`, funciones de Vercel en `fra1`.
- FastAPI es la única API de datos. El front usa Supabase para el login y valida el JWT en el backend.
- Datos personales mínimos: email de la cuenta, perfil de organización, búsquedas guardadas y conversaciones. No se ingieren personas físicas de la BDNS ni contactos personales de CORDIS.
- Las conversaciones se pueden borrar con la cuenta. Retención prevista: 12 meses.
- Analítica sin cookies. No hay banner mientras no haya cookies no esenciales.
- Anthropic procesa prompts fuera de la UE. Hace falta el contrato de encargo y las cláusulas tipo antes de enviar texto de usuarios. Los documentos de convocatorias públicas no son datos personales, pero el chat sí puede serlo.
- Una subida al asistente (perfil, borrador) es un dato del usuario. Sale del EEE, se conserva 24 horas como texto y se borra con la cuenta. No se activa para usuarios reales hasta el DPA y la retención a cero en entrenamiento.

## Consecuencias

- `docs/legal/` tiene el registro de tratamiento y la lista de encargados. No sustituye una revisión jurídica.
- `fly.toml` pide una máquina encendida para que las fichas no dependan de un arranque en frío. Supabase Pro evita la pausa del plan gratuito.

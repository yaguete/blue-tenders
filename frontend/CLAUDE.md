# Frontend

Next.js 15 App Router, React 19, Tailwind 4, shadcn/ui (Base UI). Interfaz en inglés.

## Arranque

```bash
npm run dev
npm run lint
```

`NEXT_PUBLIC_API_URL` apunta al FastAPI (por defecto `http://127.0.0.1:8000`). El front no lee Supabase salvo para el login (`NEXT_PUBLIC_SUPABASE_URL` y `NEXT_PUBLIC_SUPABASE_ANON_KEY`).

## Rutas

| Ruta | Qué es |
|---|---|
| `/` | Portada y entrada a la búsqueda. |
| `/search` | Resultados y filtros. El estado va en la query string. |
| `/opportunities/[id]` | Ficha. |
| `/funders` | Directorio de financiadores sin plazo. |
| `/compare` | Hasta 4 oportunidades (`?ids=`). |
| `/saved`, `/alerts`, `/profile` | Cuenta. Sin sesión, piden login. |
| `/assistant` | Redirige a `/?ask=1`. El chat es el panel flotante de `src/components/assistant/`, en todas las páginas. |
| `/design-lab` | Tres direcciones y el sistema. No es producto. |
| `/legal/privacy` | Privacidad. |

## Diseño

Dirección de trabajo: **Instrument** (provisional, pendiente de la sesión D.3). Tokens en `src/app/globals.css`. Las otras dos direcciones viven solo en el design lab.

Copiar no es decoración: los estados vacío, de carga y de error tienen texto propio. Sin chistes.

## i18n

Las cadenas de interfaz están en `messages/en.json`. `src/lib/i18n.ts` las lee. Añadir español es crear `messages/es.json` y un prefijo de ruta; no hace falta reescribir componentes si usan `t()`.

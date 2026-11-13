# frontend

UI de búsqueda. Pantallas mínimas del MVP:
- Listado con filtros (vertical, subsector, geografía, tipo: tender/grant, presupuesto, deadline)
- Detalle de licitación con assessment del pliego (criterios, cronograma, encaje)
- Perfil + alertas

Stack: Next.js (App Router) + Tailwind + shadcn/ui, desplegado en Vercel (ADR 0002).

## Arranque

```bash
npm install
npx shadcn@latest init
cp .env.example .env.local
npm run dev
```

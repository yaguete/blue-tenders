# Sistema de diseño

Sobre shadcn/ui y Tailwind 4. Tokens en `frontend/src/app/globals.css`. Referencia viva: `/design-lab/system`.

## Color

Roles, no hex sueltos en los componentes: `--background`, `--foreground`, `--primary`, `--muted`, `--border`, y los de estado `--status-open`, `--status-soon`, `--status-closed`, `--status-urgent`.

Confianza y procedencia: `--origin-extracted`, `--origin-generated`.

Contraste de texto sobre fondo, en claro y oscuro, por encima de 4.5:1 en los pares de cuerpo. Comprobado en el design lab con los valores oklch convertidos a sRGB relativo.

## Tipo

- Sans de interfaz, escala 12 / 14 / 16 / 20 / 28.
- Mono para ids, importes y fechas.
- Cifras tabulares en plazos e importes (`font-variant-numeric: tabular-nums`).

## Densidad

La lista de resultados usa la densidad compacta: una fila, plazo a la derecha, importe encima del título en peso medio. La ficha usa la densidad cómoda.

## Componentes de producto

En `frontend/src/components/`: `ResultRow`, `DeadlineBadge`, `MoneyRange`, `Provenance`, `EmptyState`, `ErrorState`. Los primitivos de shadcn siguen en `components/ui/`.

## Interacción

- Atajos en la búsqueda: `/` enfoca el campo, `j` y `k` mueven la selección, `s` guarda (si hay sesión), `o` abre la fuente.
- Foco visible. La interfaz se puede recorrer sin ratón.
- `prefers-reduced-motion` anula el único desplazamiento de la fila activa.
- Modo oscuro con la clase `dark` en `<html>`.

## Accesibilidad

Objetivo AA. La página de sistema lista los pares de color. Los estados no se comunican solo con color: la insignia de plazo lleva texto ("Open", "11 days", "Closed").

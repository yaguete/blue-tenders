# Direcciones visuales

Tres propuestas para elegir antes de dar la interfaz por cerrada. Los prototipos están en `/design-lab`. La aplicación usa **Instrument** de forma provisional para poder enseñar la demo; la elección se anota en [decision.md](decision.md).

Ninguna usa olas, anclas ni un azul corporativo plano. Las tres comparten la misma información: una lista densa y una ficha con plazo, importe, cofinanciación y elegibilidad en la cabecera.

## A · Almanac

Tablas de almanaque: papel, tinta, una columna de cifras bien alineada.

- Titulares: Newsreader. Interfaz: IBM Plex Sans. Cifras e ids: IBM Plex Mono.
- Papel `oklch(0.97 0.01 95)`, tinta `oklch(0.25 0.02 50)`.
- Abierta: verde kelp. Próxima: latón. Urgencia: rojo de señal, solo en el plazo.
- Tono: seco, como una tabla de mareas. El microcopy no adorna.

## B · Instrument

Instrumento de medida. Una sola tinta de acento. Las cifras mandan.

- Schibsted Grotesk y Spline Sans Mono.
- Fondo frío casi blanco, tinta azul-gris, acento `oklch(0.42 0.06 200)`.
- Los días que faltan y el importe usan una rampa corta de cmocean (balance), perceptualmente uniforme. No es un mapa: es una escala de una variable.
- Tono: preciso. "Closes in 11 days" y no "Don't miss out".

## C · Civic warmth

Para quien lee esto desde una fundación, no desde una mesa de trading.

- Fraunces y Atkinson Hyperlegible Next.
- Arena, tinta verde, coral solo en la urgencia.
- Trazos más suaves. Los estados vacíos pueden llevar un dibujo lineal; el resto de la interfaz, no.
- Tono: claro y cercano, sin exclamaciones.

## Microcopy común

- Vacío: "No calls on this heading. 14 match if you drop TRL 6–8."
- Carga: "Reading the work programme…"
- Error de fuente: "The EU portal isn't answering. Showing data from 6 h ago."
- Confianza baja: "Verify in the official call."

## Cómo elegir

En la ronda 1 de validación, 5 segundos sobre la lista y preferencia forzada entre las tres. Criterio: se lee el plazo y el importe sin buscarlos, y nadie la confunde con una plantilla de SaaS genérica. Acta en `decision.md`.

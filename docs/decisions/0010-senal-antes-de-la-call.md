# 0010 · Señal antes de la call

Fecha: 2026-11-13 · Estado: aceptada

## Contexto

Quien arma un consorcio se entera cuando la call ya lleva semanas abierta. Lo que avisa antes no es una convocatoria con plazo: es un borrador de work programme, una consulta preliminar o un plan de inversión. Stotles lo hace con los PIN de la compra pública anglosajona. Aquí el PIN ya era un tipo de ficha (`prior_information_notice`) y el estado «próxima» ya salía de esa etiqueta en el benchmark.

## Decisión

- La señal temprana es una ficha más, en el mismo índice. No hay una sección aparte.
- Es información previa: URL oficial, fecha en que se vio el cambio o se publicó el anuncio, y ningún plazo que el documento no traiga. Si trae un plazo para contestar a la consulta, se cita y no se usa como cierre de la licitación.
- Señal y convocatoria conviven. El precedente es el BOE, que avisa, y BDNS, que es la convocatoria. Una consulta de PLACSP no comparte clave con el expediente que salga después.
- En la búsqueda, esas fichas van en «Upcoming», fuera de la lista de trabajo. La lista por defecto sigue siendo lo abierto y lo que cierra en 60 días.
- Una página vigilada publica sola cuando cambia el texto, con las mismas reglas que el resto de lo scrapeado. Lo que no nombra el sector no se publica, salvo que el YAML de la página declare sus subsectores.

## Consecuencias

- `app.jobs.watch` deja de escribir borradores en la cola. La cola queda para un fallo de validación.
- Un PIN sin plazo sigue visible 90 días desde la fecha en que se vio y luego se cierra solo.

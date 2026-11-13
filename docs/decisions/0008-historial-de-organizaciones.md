# 0008 · Historial de organizaciones

Fecha: 2026-11-11 · Estado: aceptada

## Decisión

- En una subvención, la ficha enseña organizaciones de proyectos CORDIS (H2020 y Horizon Europe) parecidos. En una licitación, adjudicatarios de avisos de TED parecidos. No se inventa otra fuente. Keep.eu sigue fuera hasta que haya clave. Kohesio no entra.
- El corte del volcado y los umbrales viven en el YAML del vertical (`project_keywords`, `track_record`). El prefiltro de convocatorias no los lee.
- Una fila entra si hay evidencia: el mismo topic (y no es una convocatoria en cascada), un CPV específico compartido, o un texto parecido por encima del umbral y con subsector en común. Si nadie pasa, la lista va vacía. No se rellenan «las treinta menos malas».
- De TED no se empareja país ni identificador cuando las listas del aviso no miden lo mismo. El importe adjudicado solo se guarda si es EUR y mayor que cero. El identificador fiscal se guarda como hash, no en claro.
- De CORDIS no se guardan dirección, NIF, geolocalización ni formulario de contacto.
- «Aún no está cargado» y «nadie se parece lo bastante» son frases distintas. La segunda solo sale cuando el volcado existe.

## Consecuencias

- CORDIS tiene su job y no mueve las marcas de agua de TED, eu-ft, PLACSP ni BDNS.
- La ficha atribuye el anuncio y, si consultó el historial, CORDIS o los avisos de adjudicación de TED.
- El mismo historial se lee en el JSON local y en Supabase. `load()` de la cuenta no lo contiene.

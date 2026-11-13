# sources

Un adaptador por fuente. Contrato:

- `fetch(since)` → registros crudos
- `to_tender(raw)` → Tender canónico
- metadatos: id de fuente, tipo (api | rss | html | pdf), frecuencia, idioma

Las fuentes se rompen; cada adaptador falla de forma aislada y registra el error sin tumbar la ingesta.

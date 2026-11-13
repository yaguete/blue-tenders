# Encargados y alojamiento

Pendiente de firmar los contratos de encargo antes de tener usuarios reales. La demo local no sale de la máquina.

| Encargado | Para qué | Región prevista |
|---|---|---|
| Supabase | Postgres, Auth, Storage | eu-central-1 |
| Fly.io | API | fra |
| Vercel | Front | fra1 |
| Resend | Correo transaccional | Revisar DPA; el contenido es una alerta, no un pliego |
| Anthropic | Clasificación, extracción, análisis, chat | Fuera del EEE. No activar el chat con usuarios hasta tener el DPA y la retención a cero en entrenamiento. `ASSISTANT_PUBLIC` sigue en falso. Las subidas del chat (texto extraído, 24 h) también salen del EEE y no se usan para entrenar solo cuando ese contrato lo diga; hasta entonces el aviso del chat no lo afirma |

Atribución de fuentes en el pie de la ficha: TED, EU Funding & Tenders Portal, PLACSP, BDNS, CORDIS, y la URL concreta de cada anuncio. Si la ficha enseña historial, también atribuye el volcado de CORDIS o los avisos de adjudicación de TED. Esos adjudicatarios son organizaciones nombradas en el aviso, no contactos personales.

De los pliegos solo se muestran citas breves y el enlace al PDF original. No se republica el documento entero.

No se extraen datos de euro-access, Instrumentl, Deepbloo ni de la Commonwealth Ocean Funders Database.

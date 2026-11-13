# 0009 · Asistente flotante y documentos de la convocatoria

Fecha: 2026-11-11 · Estado: aceptada

Sustituye en parte a la 0004. Siguen vigentes las citas, la negativa a prometer elegibilidad y el streaming por SSE desde FastAPI.

## Contexto

El asistente estaba en una página y en un formulario de la ficha. Lo que se quiere es un consultor presente en todo el sitio, que al abrir una convocatoria ya haya leído sus documentos y lo enseñe, como un PDF adjunto en un chat. La 0004 preveía recuperar fragmentos. El texto de un topic europeo cabe entero.

## Decisión

- El panel flotante es la única superficie. `/assistant` redirige a la portada con el panel abierto. En la ficha queda un botón.
- Cada fuente aporta su documento, y no siempre es un PDF. El texto del topic europeo es el documento principal. Los anexos generales de Horizon se cargan una vez. El PDF de TED es el anuncio; los pliegos del comprador son un enlace y no se leen. PLACSP trae los pliegos que ya vienen en la entrada. BDNS trae la convocatoria y las bases. Una curada cuyo `url` es un PDF también lo adjunta.
- El documento se manda entero, con citas nativas por página o por sección, y caché de prompt. `search_documents` solo entra cuando no cabe. No hay enrutador ni caché de respuestas por pregunta.
- Con `DEEPSEEK_API_KEY` el mismo texto va en el mensaje y el modelo es `ASSISTANT_ANSWER_MODEL`. DeepSeek no acepta el bloque `document`, así que no hay cita nativa. Clasificar y traducir siguen en Anthropic.
- La conversación vive en el servidor y está atada a una convocatoria. El cliente manda el mensaje nuevo.
- Las subidas del usuario se guardan como texto, 24 horas, y salen del EEE. Hace falta el aviso en el chat. No se abre el asistente a usuarios reales hasta el DPA de Anthropic y la retención a cero (`ASSISTANT_PUBLIC`).
- Sin cuenta se puede ver el panel; al enviar, se pide la cuenta y se conserva la pregunta.

## Consecuencias

- La migración `0009_assistant_documents.sql` guarda texto por página, mensajes y subidas. No se guarda el binario.
- La 0007 se amplía: una subida es un dato del usuario que sale del EEE.
- El coste se registra por mensaje y hay un techo diario en dólares, no solo en número de preguntas.

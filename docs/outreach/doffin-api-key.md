# Alta de la API pública de Doffin

No está hecha. Es un registro en el portal de desarrolladores, no un correo.

1. Entrar en https://dof-notices-prod-api.developer.azure-api.net/ . La operación es **Public API → GET search**, no Notices ni download.
2. La clave no está en esa ficha. Está en **Profile → Subscriptions** (primary key). Si la lista sale vacía, hay que suscribirse al producto Public API: el botón no está dentro de la operación.
3. Guardar la clave en `DOFFIN_API_KEY` del entorno del backend. El adaptador la manda como `Ocp-Apim-Subscription-Key` en `GET /public/v2/search`.
4. Pedir avisos `COMPETITION` y `PRE_ANNOUNCEMENT`. `RESULT` no entra.
5. Leer las condiciones de uso en esa misma ficha antes de dejar la clave en producción.

Mientras no haya clave, Doffin usa la API interna de su web y lo dice en el log (`provisional`). Esa vía no está documentada como producto.

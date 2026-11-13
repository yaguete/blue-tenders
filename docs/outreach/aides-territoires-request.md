# Petición de clave de Aides-territoires

No se ha enviado. La cuenta se crea en https://aides-territoires.beta.gouv.fr/ y la clave sale en Mes paramètres → Ma clé API. No hace falta un correo a un tercero: es un alta.

---

Cuando exista la clave, va en `AIDES_TERRITOIRES_API_KEY` (todavía no leída por el código). El adaptador no está escrito. La API, comprobada el 13 nov 2026 en `/data/` y `/api/docs` (v1.8.4):

1. `POST https://aides-territoires.beta.gouv.fr/api/connexion/` con cabecera `X-AUTH-TOKEN`.
2. La respuesta trae un Bearer que caduca a las 24 h.
3. `GET https://aides-territoires.beta.gouv.fr/api/aids/all/` con `Authorization: Bearer …`.

Licencia Etalab 2.0, reutilización comercial incluida, con atribución y fecha de la última actualización. Desde marzo 2026 el servicio se centra en colectividades (un puerto sí, una empresa suelta menos). El dominio `aides-territoires.com` ya no resuelve.

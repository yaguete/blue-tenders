# Clave de Aides-territoires

La cuenta está creada. La clave va en `AIDES_TERRITOIRES_API_KEY` y el adaptador es `app/sources/aides_territoires.py`.

La API, comprobada el 13 nov 2026 en `/api/docs` (v1.8.4):

1. `POST https://aides-territoires.beta.gouv.fr/api/connexion/` con cabecera `X-AUTH-TOKEN`.
2. La respuesta trae un Bearer que caduca a las 24 h.
3. `GET https://aides-territoires.beta.gouv.fr/api/aids/?text=` con `Authorization: Bearer …`.

`/api/aids/all/` no es el listado en vivo: redirige a un volcado que se regenera cada cierto tiempo.

Licencia Etalab 2.0, reutilización comercial incluida, con atribución y fecha de la última actualización. Desde marzo 2026 el servicio se centra en colectividades (un puerto sí, una empresa suelta menos). El dominio `aides-territoires.com` ya no resuelve.

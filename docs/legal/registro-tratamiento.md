# Registro de actividades de tratamiento

Borrador operativo. No es un documento firmado ni un asesoramiento jurídico.

Responsable: el titular del proyecto blue-tender (pendiente de razón social y contacto).

| Tratamiento | Datos | Base | Conservación | Encargados |
|---|---|---|---|---|
| Cuenta | Email, identificador de Supabase Auth | Ejecución del servicio pedido al crear la cuenta | Hasta que se borra la cuenta | Supabase |
| Perfil de organización | Tipo, país, subsectores, tamaño, TRL, PIC opcional | Interés legítimo del propio usuario en el encaje; lo da él | Igual que la cuenta | Supabase, Fly |
| Alertas | Email, filtros, token de baja, consentimiento (fecha) | Consentimiento, registrado al crear la alerta | Hasta la baja | Resend, Supabase |
| Asistente | Preguntas, respuestas y ficheros que sube el usuario (solo el texto, 24 h) | Servicio pedido. No abierto a usuarios reales hasta el DPA | Mensajes: 12 meses o hasta el borrado. Subidas: 24 h | Anthropic (fuera del EEE; cláusulas tipo), Supabase |
| Analítica | Sin cookies, sin identificador cruzado, si se activa | Interés legítimo mínimo | Agregados | Por decidir; hoy no hay proveedor |

No hay decisiones automatizadas con efecto jurídico. El encaje y el asistente son orientativos y la interfaz lo dice.

Derechos: exportación `GET /me/export` y borrado `DELETE /me` con el JWT del usuario.

Las convocatorias y los socios de CORDIS son información pública de organizaciones, no un fichero de personas. La ingesta de BDNS descarta concesiones cuyo beneficiario parezca una persona física (sin razón social de organización).

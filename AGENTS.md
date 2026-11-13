# Agents

Lee [CLAUDE.md](CLAUDE.md) antes de cambiar código. Este archivo existe para herramientas que buscan `AGENTS.md`.

- Backend: [backend/CLAUDE.md](backend/CLAUDE.md)
- Frontend: [frontend/CLAUDE.md](frontend/CLAUDE.md)
- No edites el archivo del plan en `.cursor/plans/`.
- No subas secretos. `.env` no se commitea.
- La interfaz de producto está en inglés. La documentación del repo, en español.
- Añadir una fuente: adaptador en `backend/app/sources/`, fila en `docs/sources.md`, entrada en `REGISTRY`, fixture y test. El adaptador falla solo; no tumba la ingesta.
- Añadir un vertical: un YAML en `config/verticals/`. No un `if` en el pipeline.

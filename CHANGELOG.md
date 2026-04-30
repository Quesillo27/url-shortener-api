# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog.

## [1.1.1] - 2026-04-30

### Fixed
- `PATCH /api/urls/{alias}` ahora permite quitar una expiracion existente enviando `{"expires_at": null}` en lugar de ignorar el cambio.
- El endpoint de actualizacion ahora rechaza `null` explicito en `url` e `is_active` para evitar updates ambiguos.

## [1.1.0] - 2026-04-23

### Added
- Endpoint `PATCH /api/urls/{alias}` para actualizar URL destino, expiracion o estado.
- Filtros `search` e `include_expired` en `GET /api/urls`.
- Metricas de salud con uptime, errores y latencia promedio.
- Middleware de rate limiting en memoria y headers de seguridad.
- Workflow de CI, `.env.example`, `setup.sh`, `ARCHITECTURE.md` y ejemplos de uso.

### Changed
- Refactor a paquete `app/` con modulos de configuracion, base de datos, esquemas, servicios y app.
- Dockerfile ahora usa multi-stage build y usuario no root.
- Makefile ampliado con targets de DX.

### Fixed
- Ejecucion de `pytest` ahora es estable con `pytest.ini` y ruta del proyecto explicita.
- Validacion de URL mas estricta en creacion y actualizacion.

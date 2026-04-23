# Architecture

## Objetivo

La API expone un acortador de URLs ligero sobre FastAPI y SQLite, manteniendo un solo binario de despliegue pero separando responsabilidades para facilitar pruebas y evolucion.

## Estructura

- `app/config.py`: configuracion centralizada por variables de entorno.
- `app/database.py`: conexion SQLite compartida, locking e inicializacion de esquema.
- `app/schemas.py`: validaciones de entrada y modelos de request.
- `app/services.py`: logica de negocio para CRUD, redireccion y estadisticas.
- `app/main.py`: ensamblaje FastAPI, middlewares y rutas.
- `main.py`: shim de compatibilidad para `uvicorn main:app` y tests existentes.

## Decisiones

- SQLite se mantiene para conservar arranque simple y despliegue sin servicios externos.
- El rate limiting es en memoria para cubrir abuso basico sin introducir Redis.
- Se preservan las respuestas de endpoints existentes para no romper clientes actuales.

## Trade-offs

- El rate limiting en memoria no comparte estado entre replicas.
- La base SQLite con lock global prioriza simplicidad sobre throughput extremo.

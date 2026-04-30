# url-shortener-api

![CI](https://github.com/Quesillo27/url-shortener-api/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-orange)

API REST para acortar URLs con alias personalizados, expiracion, estadisticas de clics y mantenimiento basico del enlace. Construida con FastAPI + SQLite, lista para correr localmente o en Docker sin servicios externos.

## Instalacion en 3 comandos

```bash
git clone https://github.com/Quesillo27/url-shortener-api
cd url-shortener-api
./setup.sh
```

## Uso rapido

```bash
uvicorn main:app --reload
# Swagger UI: http://localhost:8000/docs
```

## Ejemplos reales

```bash
# Crear URL corta
curl -s -X POST http://localhost:8000/shorten \
  -H "Content-Type: application/json" \
  -d '{"url":"https://github.com/Quesillo27","alias":"gh"}'

# Buscar URLs por alias o destino
curl -s "http://localhost:8000/api/urls?search=gh&active_only=true"

# Actualizar destino de una URL existente
curl -s -X PATCH http://localhost:8000/api/urls/gh \
  -H "Content-Type: application/json" \
  -d '{"url":"https://github.com/Quesillo27/url-shortener-api"}'

# Quitar la expiracion de una URL existente
curl -s -X PATCH http://localhost:8000/api/urls/gh \
  -H "Content-Type: application/json" \
  -d '{"expires_at":null}'

# Ver salud y metricas
curl -s http://localhost:8000/health
```

## API

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| GET | `/health` | Estado del servicio, uptime y metricas basicas |
| POST | `/shorten` | Crear URL corta |
| GET | `/{alias}` | Redirigir y registrar clic |
| GET | `/api/urls` | Listar URLs con paginacion, `search`, `active_only`, `include_expired` |
| GET | `/api/urls/{alias}` | Obtener una URL |
| PATCH | `/api/urls/{alias}` | Actualizar destino, expiracion o estado. Enviar `{"expires_at": null}` para quitar expiracion |
| GET | `/api/urls/{alias}/stats` | Estadisticas de clics y ultimo acceso |
| DELETE | `/api/urls/{alias}` | Desactivar URL |
| GET | `/api/stats/global` | Resumen global y top URLs |

## Variables de entorno

| Variable | Descripcion | Default | Obligatoria |
|----------|-------------|---------|-------------|
| `PORT` | Puerto del servidor | `8000` | No |
| `DB_PATH` | Ruta al archivo SQLite | `urls.db` | No |
| `BASE_URL` | URL base usada en `short_url` | `http://localhost:8000` | No |
| `ALIAS_LENGTH` | Longitud del alias auto-generado | `6` | No |
| `MAX_CLICKS_HISTORY` | Maximo de clics recientes en stats | `100` | No |
| `LOG_LEVEL` | Nivel de logging | `INFO` | No |
| `RATE_LIMIT_WINDOW_SECONDS` | Ventana del rate limit | `60` | No |
| `RATE_LIMIT_MAX_REQUESTS` | Requests por IP en la ventana | `120` | No |

## Docker

```bash
docker build -t url-shortener-api .
docker run --rm -p 8000:8000 -v $(pwd)/data:/data url-shortener-api
```

## DX

```bash
make dev
make test
make build
make docker
```

## Roadmap

- Persistencia compartida para rate limiting en despliegues multi-instancia.
- Exportacion de estadisticas agregadas en CSV o JSON descargable.
- Soporte opcional para PostgreSQL si el volumen de trafico supera SQLite.

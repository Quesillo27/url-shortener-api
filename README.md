# url-shortener-api

![Python](https://img.shields.io/badge/Python-3.12+-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green) ![SQLite](https://img.shields.io/badge/SQLite-embebido-lightgrey) ![License](https://img.shields.io/badge/license-MIT-orange)

API REST para acortar URLs con alias personalizados, expiración, estadísticas de clics por día y top URLs. Construida con FastAPI + SQLite — sin dependencias externas, lista para Docker.

## Instalación en 3 comandos

```bash
git clone https://github.com/Quesillo27/url-shortener-api
cd url-shortener-api
pip install -r requirements.txt
```

## Uso

```bash
uvicorn main:app --reload   # inicia el servidor en puerto 8000
# Documentación interactiva: http://localhost:8000/docs
```

## Ejemplo

```bash
# 1. Acortar una URL
curl -s -X POST http://localhost:8000/shorten \
  -H "Content-Type: application/json" \
  -d '{"url": "https://github.com/Quesillo27", "alias": "gh"}'
# → {"alias":"gh","short_url":"http://localhost:8000/gh","click_count":0,...}

# 2. Redirigir (vía browser o curl -L)
curl -L http://localhost:8000/gh
# → redirige a https://github.com/Quesillo27

# 3. Ver estadísticas
curl http://localhost:8000/api/urls/gh/stats
# → {"total_clicks":1,"clicks_by_day":[{"day":"2026-04-14","count":1}],...}
```

## API — Endpoints disponibles

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/health` | Estado del servicio |
| POST | `/shorten` | Crear URL corta |
| GET | `/{alias}` | Redirigir (registra clic) |
| GET | `/api/urls` | Listar URLs con paginación |
| GET | `/api/urls/{alias}` | Obtener info de una URL |
| GET | `/api/urls/{alias}/stats` | Estadísticas de clics (30 días, histórico) |
| DELETE | `/api/urls/{alias}` | Desactivar URL (borrado lógico) |
| GET | `/api/stats/global` | Estadísticas globales + top 5 URLs |
| GET | `/docs` | Documentación Swagger UI |

## Body para POST /shorten

```json
{
  "url": "https://ejemplo.com",          // requerido
  "alias": "mi-link",                    // opcional (3-50 chars, [a-zA-Z0-9-_])
  "expires_at": "2026-12-31T23:59:59Z"  // opcional (ISO 8601)
}
```

## Variables de entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `PORT` | `8000` | Puerto del servidor |
| `DB_PATH` | `urls.db` | Ruta al archivo SQLite |
| `BASE_URL` | `http://localhost:8000` | URL base para generar short links |
| `ALIAS_LENGTH` | `6` | Longitud de alias auto-generados |
| `MAX_CLICKS_HISTORY` | `100` | Máx. clics recientes en /stats |

## Docker

```bash
docker build -t url-shortener-api .
docker run -p 8000:8000 -v $(pwd)/data:/data url-shortener-api
```

## Contribuir

PRs bienvenidos. Corre `make test` antes de enviar.

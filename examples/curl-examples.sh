#!/bin/sh
set -eu

BASE_URL="${BASE_URL:-http://localhost:8000}"

curl -s -X POST "$BASE_URL/shorten" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://github.com/Quesillo27","alias":"gh-demo"}'
printf '\n'

curl -s "$BASE_URL/api/urls?search=gh&active_only=true"
printf '\n'

curl -s -X PATCH "$BASE_URL/api/urls/gh-demo" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://github.com/Quesillo27/url-shortener-api"}'
printf '\n'

curl -s -X PATCH "$BASE_URL/api/urls/gh-demo" \
  -H "Content-Type: application/json" \
  -d '{"expires_at":null}'
printf '\n'

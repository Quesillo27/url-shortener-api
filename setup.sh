#!/bin/sh
set -eu

python3 -m pip install -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
fi

printf 'Proyecto listo. Edita .env si necesitas cambiar la configuracion.\n'

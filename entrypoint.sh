#!/bin/bash

# Создаем директорию для логов, если её нет
mkdir -p /app/logs

python manage.py migrate --check
status=$?
if [[ $status != 0 ]]; then
    python manage.py migrate
fi
yes | python manage.py collectstatic
exec "$@"
#!/bin/bash

gunicorn RentalGuru.wsgi:application --bind 0.0.0.0:8000 --workers 4 &
daphne -b 0.0.0.0 -p 8001 RentalGuru.asgi:application
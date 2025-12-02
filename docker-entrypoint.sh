#!/bin/sh
set -e

# Apply database migrations to ensure the schema is up to date before
# starting the application server. This prevents runtime errors from
# pending migrations when the container boots with a fresh database.
python jobtracker/manage.py migrate --noinput

# Start Gunicorn inside the Django project directory so settings load
# correctly.
exec gunicorn --chdir jobtracker jobtracker.wsgi:application --bind 0.0.0.0:${PORT:-8000}

#!/bin/sh
set -e
cd /app
echo "Running database migrations (alembic upgrade head)..."
python -m alembic upgrade head
exec "$@"

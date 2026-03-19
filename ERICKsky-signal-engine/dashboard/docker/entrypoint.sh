#!/bin/sh
set -e

echo "[entrypoint] Starting ERICKsky Dashboard..."

# Always work from the Laravel root
cd /var/www/html

# Wait for PostgreSQL port to open (max 60s)
echo "[entrypoint] Waiting for PostgreSQL..."
for i in $(seq 1 30); do
    nc -z postgres 5432 2>/dev/null && break
    echo "[entrypoint] PostgreSQL not ready yet ($i/30)..."
    sleep 2
done
echo "[entrypoint] PostgreSQL is up."

# Run database migrations (reads DB credentials from .env automatically)
echo "[entrypoint] Running migrations..."
php artisan migrate --force

# Cache config / routes / views for production performance
echo "[entrypoint] Caching config, routes, views..."
php artisan config:cache
php artisan route:cache
php artisan view:cache

echo "[entrypoint] Setup complete. Starting supervisord..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf

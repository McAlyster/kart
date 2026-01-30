#!/bin/sh

echo "⏳ Waiting for PostgreSQL at $POSTGRES_HOST:$POSTGRES_PORT..."

#while ! nc -z "$POSTGRES_HOST" "$POSTGRES_PORT"; do
#  sleep 1
# done


# Install omz
sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"


echo "✅ PostgreSQL is up. Running migrations..."
python manage.py migrate --noinput

echo "📦 Collecting static files..."
python manage.py collectstatic --noinput

echo "🚀 Starting: $@"
exec "$@"

#!/bin/bash
set -e  # Exit immediately if any command fails

echo "🚀 Running automatic database migrations..."
python run_migrations.py

if [ $? -eq 0 ]; then
    echo "✅ Migrations complete, starting web server..."
    exec uvicorn backend.app:application --host 0.0.0.0 --port ${PORT:-8000}
else
    echo "❌ Migrations failed, aborting startup"
    exit 1
fi

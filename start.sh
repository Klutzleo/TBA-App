#!/bin/bash
set -e  # Exit immediately if any command fails

echo "🔧 Running database migration..."
python backend/migrations/001_add_sw_and_npcs.py

if [ $? -eq 0 ]; then
    echo "✅ Migration successful, starting web server..."
    exec uvicorn backend.app:application --host 0.0.0.0 --port ${PORT:-8000}
else
    echo "❌ Migration failed, aborting startup"
    exit 1
fi

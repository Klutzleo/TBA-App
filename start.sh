#!/bin/bash
set -e  # Exit immediately if any command fails

echo "🚀 Running automatic database migrations..."
python run_migrations.py || echo "⚠️ Migrations failed or not found"

echo "🔧 Force-fixing database constraints..."
python backend/force_fix_constraints.py

echo "🔧 Fixing campaign trigger..."
python backend/fix_trigger.py

echo "🔧 Checking for test campaign..."
python backend/bootstrap_test_data.py

echo "✅ Bootstrap complete, starting web server..."
exec uvicorn backend.app:application --host 0.0.0.0 --port ${PORT:-8000}

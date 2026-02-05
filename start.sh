#!/bin/bash
set -e  # Exit immediately if any command fails

echo "🚀 Running automatic database migrations..."
python run_migrations.py || echo "⚠️ Migrations failed or not found"

echo "🔐 Running authentication migration..."
python backend/migrations/add_auth_tables.py

# Band-aid scripts removed - not needed on clean database
# echo "🔧 Force-fixing database constraints..."
# python backend/force_fix_constraints.py
# echo "🔧 Fixing campaign trigger (if needed)..."
# python backend/fix_trigger.py || echo "⚠️ Trigger fix skipped"

# Disabled bootstrap test data - test real campaign creation instead
# echo ""
# echo "======================================================================"
# echo "🎯 BOOTSTRAPPING TEST CAMPAIGN"
# echo "======================================================================"
# python backend/bootstrap_test_data.py || python backend/manual_bootstrap.py
# echo "======================================================================"
# echo ""

echo "🚀 Starting web server..."
exec uvicorn backend.app:application --host 0.0.0.0 --port ${PORT:-8000}

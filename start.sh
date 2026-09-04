#!/bin/bash
set -e  # Exit immediately if any command fails

echo "🚀 Running database migrations..."
python run_migrations.py

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
# --proxy-headers/--forwarded-allow-ips: Railway's edge proxy is the only thing
# that can reach this container, so trust its X-Forwarded-For. Without this,
# uvicorn leaves request.client.host as the proxy hop, not the real client IP —
# slowapi's get_remote_address() (used for every @limiter.limit()) keys off
# that, so rate limiting was silently non-functional in prod.
exec uvicorn backend.app:application --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'

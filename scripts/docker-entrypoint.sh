#!/bin/sh
set -e

echo "▶ ENTRYPOINT: Starting container diagnostics"
echo "Python: $(python --version 2>&1)"
echo "Working dir: $(pwd)"

echo "▶ Environment vars status"
if [ -z "$DATABASE_URL" ]; then
  echo "DATABASE_URL: MISSING"
else
  echo "DATABASE_URL: PRESENT ($DATABASE_URL)"
fi

if [ -z "$API_KEY" ]; then
  echo "API_KEY: MISSING"
else
  echo "API_KEY: PRESENT"
fi

echo "▶ Verifying application import (this will raise an error if imports fail)"
python - <<'PY'
try:
    import backend.app
    print('backend.app imported successfully')
except Exception as e:
    import traceback, sys
    traceback.print_exc()
    sys.exit(1)
PY

echo "▶ Launching Uvicorn"
exec uvicorn backend.app:application --host 0.0.0.0 --port 8000 --workers 1
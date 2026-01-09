release: python backend/migrations/001_add_sw_and_npcs.py
web: uvicorn backend.app:application --host 0.0.0.0 --port ${PORT:-8000}
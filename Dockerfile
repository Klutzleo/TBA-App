# Dockerfile

# 1. Base image with Python
FROM python:3.11-slim

# 2. Set working dir & copy code
WORKDIR /app
COPY . .

# 3. Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# 4. Expose the web port
EXPOSE 8080

# 5. Define a container health check on /health, not /
HEALTHCHECK --start-period=5s --interval=10s --retries=3 \
  CMD curl --fail http://localhost:8080/health || exit 1

# 6. Launch Gunicorn (shell form so $PORT expands)
CMD gunicorn backend.app:application --bind 0.0.0.0:$PORT --workers 1 --threads 4
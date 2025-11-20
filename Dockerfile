# 1. Base image with Python
FROM python:3.11-slim

# 2. Set working dir & copy code
WORKDIR /app
COPY . .

# 3. Install dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir flasgger

# 4. Expose the fixed port
EXPOSE 8080

# 5. Healthcheck against your Flask /health on 8080
# Give the container a longer startup window; some platforms run healthchecks
# very quickly after container start. Increase start-period and retries so
# transient import/DB waits don't mark the container unhealthy immediately.
HEALTHCHECK --start-period=30s --interval=10s --retries=5 \
  CMD curl --fail http://localhost:8080/health || exit 1

# 6. Use an entrypoint script that prints diagnostics and attempts an import
# before launching Gunicorn. This surfaces import-time errors to container logs.
RUN chmod +x /app/scripts/docker-entrypoint.sh
CMD ["/app/scripts/docker-entrypoint.sh"]
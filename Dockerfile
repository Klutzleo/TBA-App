# 1. Base image with Python
FROM python:3.11-slim

# 2. Set working dir & copy code
WORKDIR /app
COPY . .

# 3. Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# 4. Expose the web port
EXPOSE 8080

# 5. Define a container health check
#    Wait 5s before first check, then every 10s, allow 3 retries
HEALTHCHECK --start-period=5s --interval=10s --retries=3 \
  CMD curl --fail http://localhost:8080/ || exit 1

# 6. Launch Gunicorn in the foreground, bound to $PORT
CMD ["gunicorn", "backend.app:application", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "4"]
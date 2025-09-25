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
HEALTHCHECK --start-period=5s --interval=10s --retries=3 \
  CMD curl --fail http://localhost:8080/health || exit 1

# 6. Launch Gunicorn binding to 0.0.0.0:8080
CMD ["sh", "-c", "echo \"▶ Binding to port 8080\"; exec gunicorn backend.app:application --bind 0.0.0.0:8080 --workers 1 --threads 4"]
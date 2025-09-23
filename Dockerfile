# 1. Base image with Python
FROM python:3.11-slim

# 2. Set working dir & copy code
WORKDIR /app
COPY . .

# 3. Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# 4. Expose any default port (optional)
EXPOSE 8080

# 5. Healthcheck against your Flask /health
HEALTHCHECK --start-period=5s --interval=10s --retries=3 \
  CMD curl --fail http://localhost:8080/health || exit 1

# 6. Launch Gunicorn via sh -c so $PORT expands at runtime
CMD ["sh","-c","echo \"▶ PORT is $PORT\"; gunicorn backend.app:application --bind 0.0.0.0:$PORT --workers 1 --threads 4"]
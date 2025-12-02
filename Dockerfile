# Use official Python image.
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=America/New_York

# Install system packages
RUN apt-get update && apt-get install -y --no-install-recommends tzdata && rm -rf /var/lib/apt/lists/*

# Install dependencies
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Collect static files
RUN python jobtracker/manage.py collectstatic --noinput || true

# Copy entrypoint script that applies migrations before starting the server.
COPY docker-entrypoint.sh ./

# Run the application. The entrypoint ensures migrations are applied so the
# app does not fail with a 500 due to missing schema changes when the
# container boots with a fresh database.
CMD ["./docker-entrypoint.sh"]

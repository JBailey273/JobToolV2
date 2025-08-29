# Use official Python image.
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install dependencies
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Collect static files
RUN python jobtracker/manage.py collectstatic --noinput || true

# Run the application. The Django project resides in the nested
# `jobtracker` package, so reference its WSGI module explicitly.
CMD gunicorn jobtracker.jobtracker.wsgi:application --bind 0.0.0.0:$PORT

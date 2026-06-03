FROM python:3.11-slim

WORKDIR /app

# Install dependencies (layer cached unless requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Create non-root user
RUN adduser --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser

# Database and log directories
RUN mkdir -p logs

EXPOSE 8000

# Production: gunicorn with uvicorn workers — PORT is set by Railway
CMD ["gunicorn", "dashboard.app:app", "--worker-class", "uvicorn.workers.UvicornWorker", "--workers", "2", "--bind", "0.0.0.0:8000", "--access-logfile", "-", "--error-logfile", "-"]

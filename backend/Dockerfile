# Backend Dockerfile for news-scraper
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create backend directory structure
RUN mkdir -p /app/backend

# Install Python dependencies
COPY pyproject.toml ./backend/
RUN pip install --upgrade pip && \
    cd backend && pip install .

# Download spaCy model
RUN python -m spacy download en_core_web_sm

# Copy application code
COPY . ./backend/

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app
USER appuser

# Set working directory to backend
WORKDIR /app

# Expose port
EXPOSE 8000

# Default command
CMD ["uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PYTHONPATH=/app

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency definitions first for Docker build caching
COPY pyproject.toml ./
COPY requirements-windows-dev.txt ./

# Copy the Python package before installing it in editable mode
COPY app ./app

# Install all application dependencies
RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install --no-cache-dir -r requirements-windows-dev.txt \
    && python -m pip install --no-cache-dir -e .

# Copy Alembic configuration and migrations
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic

# Copy runtime directories required by PetroEdge AI
COPY models ./models
COPY model_store ./model_store
COPY dataset_store ./dataset_store
COPY experiment_store ./experiment_store

RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
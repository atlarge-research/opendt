FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy and install dependencies from root pyproject.toml
COPY pyproject.toml /app/pyproject.toml
RUN pip install --no-cache-dir -e /app

# Copy and install shared library
COPY libs/common /app/libs/common
RUN pip install --no-cache-dir -e /app/libs/common

# Copy service code
COPY services/opendt-api /app/services/opendt-api

# Create non-root user for security
RUN useradd -m -u 1000 opendt && \
    chown -R opendt:opendt /app

USER opendt

# Set working directory to service for proper module resolution
WORKDIR /app/services/opendt-api

# Expose the API port
EXPOSE 8000

CMD ["uvicorn", "opendt_api.main:app", "--host", "0.0.0.0", "--port", "8000"]

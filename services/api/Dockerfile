FROM python:3.11.14-slim

WORKDIR /app

# Copy and install dependencies from root pyproject.toml
COPY pyproject.toml constraints.txt /app/
RUN pip install --no-cache-dir -c /app/constraints.txt -e /app

# Copy and install shared library
COPY libs/common /app/libs/common
RUN pip install --no-cache-dir -c /app/constraints.txt -e /app/libs/common

# Copy service code
COPY services/api /app/services/api

# Create non-root user for security
RUN useradd -m -u 1000 opendt && \
    chown -R opendt:opendt /app

USER opendt

# Set working directory to service for proper module resolution
WORKDIR /app/services/api

# Expose the API port
EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

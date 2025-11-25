FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including Java for OpenDC
RUN apt-get update && apt-get install -y \
    gcc \
    openjdk-21-jre-headless \
    && rm -rf /var/lib/apt/lists/*

# Copy and install dependencies from root pyproject.toml
COPY pyproject.toml /app/pyproject.toml
RUN pip install --no-cache-dir -e /app

# Copy and install shared library
COPY libs/common /app/libs/common
RUN pip install --no-cache-dir -e /app/libs/common

# Copy service code
COPY services/sim-worker/sim_worker /app/services/sim-worker/sim_worker

# Copy OpenDC binaries (these will be in the image)
COPY services/sim-worker/opendc /app/opendc

# Create output directory for OpenDC results
RUN mkdir -p /app/output && chmod 755 /app/output

# Create non-root user for security
RUN useradd -m -u 1000 opendt && \
    chown -R opendt:opendt /app && \
    chmod +x /app/opendc/bin/OpenDCExperimentRunner/bin/OpenDCExperimentRunner

USER opendt

# Set working directory to service for proper module resolution
WORKDIR /app/services/sim-worker

CMD ["python", "-m", "sim_worker.main"]

FROM python:3.11-slim

WORKDIR /app

# Install minimal dependencies
RUN pip install --no-cache-dir \
    kafka-python==2.0.2 \
    pyyaml==6.0.1 \
    pydantic==2.5.0

# Copy and install shared library
COPY libs/common /app/libs/common
RUN pip install --no-cache-dir -e /app/libs/common

# Copy service code
COPY services/kafka-init /app/services/kafka-init

# Create non-root user for security
RUN useradd -m -u 1000 opendt && \
    chown -R opendt:opendt /app

USER opendt

# Set working directory to service for proper module resolution
WORKDIR /app/services/kafka-init

CMD ["python", "-m", "kafka_init.main"]

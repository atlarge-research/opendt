FROM python:3.11.14-slim

WORKDIR /app

# Copy and install shared library
COPY constraints.txt /app/constraints.txt
COPY libs/common /app/libs/common
RUN pip install --no-cache-dir -c /app/constraints.txt -e /app/libs/common

# Copy service code
COPY services/kafka-init /app/services/kafka-init

# Create non-root user for security
RUN useradd -m -u 1000 opendt && \
    chown -R opendt:opendt /app

USER opendt

# Set working directory to service for proper module resolution
WORKDIR /app/services/kafka-init

CMD ["python", "-m", "kafka_init.main"]

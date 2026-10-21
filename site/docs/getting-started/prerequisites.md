---
sidebar_position: 1
---

# Prerequisites

Before running OpenDT, ensure you have the following installed:

## Required Software

| Software | Version | Purpose |
|----------|---------|---------|
| Docker | 20.10+ | Container runtime |
| Docker Compose | 2.0+ | Multi-container orchestration |
| Make | Any | Build automation |
| Python | 3.11+ | OpenDT CLI and plot scripts |
| uv | Any | Python environment (`make setup`) |

On Windows, use WSL2: the Makefile runs POSIX shell commands.

## Verify Installation

```bash
docker --version
docker compose version
make --version
python3 --version
uv --version
```

## System Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| RAM | 8 GB | 16 GB |
| CPU | 4 cores | 8 cores |
| Disk | 10 GB | 20 GB |

OpenDT runs multiple containers including Kafka, Grafana, and the simulation services. More RAM and CPU cores will improve performance, especially for faster simulation speeds. With calibration on, Docker needs at least 8 GB of memory (in Docker Desktop:
Settings, Resources).

## Network Ports

OpenDT uses the following ports by default:

| Port | Service |
|------|---------|
| 3000 | Grafana Dashboard |
| 3001 | API (OpenAPI/Swagger) |
| 9092 | Kafka (from the host) |
| 9093 | Kafka controller |

Ensure these ports are available before starting.

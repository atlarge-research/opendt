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

## Verify Installation

```bash
docker --version
docker compose version
make --version
```

## System Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| RAM | 8 GB | 16 GB |
| CPU | 4 cores | 8 cores |
| Disk | 10 GB | 20 GB |

OpenDT runs multiple containers including Kafka, Grafana, and the simulation services. More RAM and CPU cores will improve performance, especially for faster simulation speeds.

## Network Ports

OpenDT uses the following ports by default:

| Port | Service |
|------|---------|
| 3000 | Grafana Dashboard |
| 3001 | API (OpenAPI/Swagger) |
| 9092 | Kafka (internal) |

Ensure these ports are available before starting.

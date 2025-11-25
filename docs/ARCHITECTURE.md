# OpenDT Architecture

Welcome to the OpenDT documentation! This document provides a comprehensive overview of the system's architecture, design principles, and core concepts.

## Table of Contents

- [System Overview](#system-overview)
- [Architecture Diagram](#architecture-diagram)
- [Services](#services)
- [Data Flow](#data-flow)
- [Kafka Topics](#kafka-topics)
- [Related Documentation](#related-documentation)

## System Overview

**OpenDT** (Open Digital Twin) is a distributed system for datacenter simulation and What-If analysis. It operates in "Shadow Mode" by replaying historical workload data through the OpenDC simulator to compare predicted vs. actual power consumption.

### Key Objectives

1. **Power Consumption Prediction**: Simulate datacenter power usage based on workload patterns
2. **What-If Analysis**: Answer questions like "What happens if we upgrade CPU architecture?" without touching live hardware
3. **Infrastructure Optimization**: Identify opportunities for energy efficiency improvements
4. **Real-time Comparison**: Continuously compare simulation predictions against actual telemetry

### Core Capabilities

- Event-time windowing with configurable window sizes (default: 5 minutes)
- Cumulative simulation for accurate long-running predictions
- Topology management (real vs. simulated configurations)
- Result caching to avoid redundant simulations
- Multiple operating modes (normal, debug, experiment)
- Dynamic plot generation for power consumption analysis

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          OpenDT System                               │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────┐     ┌────────────────────────────────────┐
│   dc-mock    │────>│            Kafka Bus               │
│  (Producer)  │     │  ┌──────────────────────────────┐  │
│              │     │  │ Topics:                      │  │
│ Reads:       │     │  │  • dc.workload (tasks)       │  │
│  - tasks     │     │  │  • dc.power (telemetry)      │  │
│  - fragments │     │  │  • dc.topology (real)        │  │
│  - power     │     │  │  • sim.topology (simulated)  │  │
│  - topology  │     │  │  • sim.results (predictions) │  │
└──────────────┘     │  │  • sys.config (runtime cfg)  │  │
                     │  └──────────────────────────────┘  │
                     └───────┬────────────────────────────┘
                             │
                   ┌─────────┴─────────────┐
                   │                       │
          ┌────────▼──────┐     ┌─────────▼────────┐
          │  sim-worker   │     │   dashboard      │
          │  (Consumer)   │     │   (FastAPI)      │
          │               │     │                  │
          │ • Windows     │     │ • Web UI         │
          │ • OpenDC      │     │ • REST API       │
          │ • Caching     │◀────│ • Topology Mgmt  │
          │ • Experiments │     │                  │
          └───────┬───────┘     └─────────┬────────┘
                  │                       │
                  │              ┌────────▼────────┐
                  │              │   PostgreSQL    │
                  │              │   (TimescaleDB) │
                  │              └─────────────────┘
                  │
          ┌───────▼───────┐
          │ Experiment    │
          │ Output:       │
          │  • Parquet    │
          │  • Plots      │
          │  • Archives   │
          └───────────────┘
```

## Services

OpenDT consists of 5 microservices orchestrated via Docker Compose:

### 1. dc-mock (Datacenter Mock)

**Purpose**: Simulates a real datacenter by replaying historical data

**Location**: [`../services/dc-mock/`](../services/dc-mock/README.md)

**Key Features**:
- Reads Parquet files (`tasks`, `fragments`, `consumption`) from `data/<WORKLOAD>/`
- Publishes to Kafka with configurable speed factor (e.g., 300x real-time)
- Three independent producers: Workload, Power, Topology
- Heartbeat mechanism for window synchronization

**Produces To**:
- `dc.workload` - Task submissions + periodic heartbeats
- `dc.power` - Power consumption telemetry
- `dc.topology` - Real datacenter topology snapshots

---

### 2. sim-worker (Simulation Engine)

**Purpose**: Core simulation worker that bridges Kafka and OpenDC simulator

**Location**: [`../services/sim-worker/`](../services/sim-worker/README.md)

**Key Features**:
- Event-time windowing with heartbeat-driven closing
- Cumulative simulation (re-simulates all tasks from beginning)
- Result caching based on topology hash + task count
- Multiple operating modes (normal, debug, experiment)
- Integration with OpenDC binary (Java-based simulator)

**Consumes From**:
- `dc.workload` - Tasks and heartbeats
- `dc.topology` - Real topology snapshots
- `sim.topology` - Simulated topology updates
- `dc.power` - Actual power (experiment mode)

**Produces To**:
- `sim.results` - Simulation predictions (normal mode)
- Local files - Results and archives (debug/experiment mode)

---

### 3. dashboard (Web Dashboard)

**Purpose**: Web dashboard and REST API for system control and visualization

**Location**: [`../services/dashboard/`](../services/dashboard/README.md)

**Key Features**:
- Web UI for real-time visualization
- FastAPI with automatic OpenAPI documentation
- Topology management endpoint (`PUT /api/topology`)
- Health check and status endpoints
- Kafka producer for configuration updates
- Static file serving for dashboard assets

**Routes**:
- `GET /` - Web dashboard UI
- `GET /health` - Health check (Kafka + config status)
- `GET /docs` - Interactive Swagger UI
- `PUT /api/topology` - Update simulated datacenter topology

---

### 4. kafka-init (Infrastructure Initialization)

**Purpose**: Creates Kafka topics with proper retention and compaction policies

**Location**: [`../services/kafka-init/`](../services/kafka-init/README.md)

**Key Features**:
- Reads topic configuration from YAML
- Creates topics on Kafka startup
- Applies retention policies and compaction settings
- Fail-fast on errors

---

## Data Flow

### 1. Data Ingestion

```
data/SURF/
├── tasks.parquet      ─┐
├── fragments.parquet  ─┤──> dc-mock ──> dc.workload (Kafka)
├── consumption.parquet─┤──> dc-mock ──> dc.power (Kafka)
└── topology.json      ─┘──> dc-mock ──> dc.topology (Kafka)
```

### 2. Simulation Pipeline

```
dc.workload ──┐
              ├──> sim-worker ──> OpenDC ──> results
dc.topology ──┤                    (binary)
sim.topology ─┘
```

### 3. Window Processing

1. **Task Arrival**: Tasks published to `dc.workload` with submission timestamps
2. **Window Assignment**: Task assigned to window based on rounded submission time
3. **Heartbeat Signal**: Periodic heartbeat messages indicate time progression
4. **Window Closing**: When heartbeat timestamp ≥ window end, close window
5. **Simulation**: Invoke OpenDC with cumulative tasks + simulated topology
6. **Caching**: Check if topology + task count match previous simulation
7. **Output**: Publish results or write to files based on operating mode

### 4. Topology Management

```
User/Dashboard ──> PUT /api/topology ──> sim.topology (Kafka) ──> sim-worker
                                                                │
                                                                ├──> Update simulated topology
                                                                ├──> Clear result cache
                                                                └──> Use for future simulations
```

## Kafka Topics

### Topic Overview

| Topic | Type | Purpose | Retention | Key |
|-------|------|---------|-----------|-----|
| `dc.workload` | Stream | Task submissions + heartbeats | 24 hours | null |
| `dc.power` | Stream | Actual power telemetry | 1 hour | null |
| `dc.topology` | Compacted | Real datacenter topology | 1h lag | `datacenter` |
| `sim.topology` | Compacted | Simulated topology (What-If) | 0ms lag | `datacenter` |
| `sys.config` | Compacted | Runtime configuration | infinite | setting key |
| `sim.results` | Stream | Simulation predictions | 7 days | null |

### Compaction Strategy

**Compacted topics** (`dc.topology`, `sim.topology`, `sys.config`) keep only the latest value per key:
- Ensures consumers always get current state
- Enables efficient state recovery
- Reduces storage for infrequently changing data

**Stream topics** (`dc.workload`, `dc.power`, `sim.results`) retain all messages up to retention period:
- Preserves full event history
- Enables time-travel and replay
- Supports multiple consumers at different offsets

## Related Documentation

### Service Documentation
- [dc-mock README](../services/dc-mock/README.md) - Datacenter mock producer
- [sim-worker README](../services/sim-worker/README.md) - Simulation engine
- [dashboard README](../services/dashboard/README.md) - Web dashboard and API
- [kafka-init README](../services/kafka-init/README.md) - Kafka initialization

### Concept Documentation
- [Data Models](./DATA_MODELS.md) - Pydantic models and data structures

### Development Resources
- [Root README](../README.md) - Quick start and setup
- [Makefile Commands](../Makefile) - Available `make` commands
- [Common Library](../libs/common/opendt_common/) - Shared Pydantic models and utilities

---
sidebar_position: 5
---

# Architecture

OpenDT follows a modular architecture designed for datacenter digital twins. This page explains the high-level and detailed design.

## High-Level Design

![OpenDT High-Level Architecture](/img/design_opendt_hl.png)

The architecture consists of six main components:

### Physical Infrastructure (P)

The **Datacenter Twin** represents the real physical infrastructure being monitored. In OpenDT, this is simulated by the **dc-mock** service, which replays historical workload and power data.

### Front-end (B)

The **Interfaces** component provides user access to the system. OpenDT implements this through:

- **Grafana Dashboard** - Three screens of power, CO₂, jobs, and the twin's accuracy, with a control panel that changes
  the running twin
- **REST API** - Programmatic access for querying data and controlling topology

### Orchestration (C)

The **Orchestrator** coordinates the flow of data between components. In OpenDT, **Kafka** serves as the message broker that enables this orchestration, with topics for workload, power, and topology (`dc.*`), the simulated topology (`sim.topology`), and runtime settings
(`sys.config`).

### Data Platform (D, E)

- **Telemetry (D)** - Power consumption data from the physical infrastructure
- **Data Management (E)** - Storage and aggregation of simulation results in Parquet files

### Simulator (F, G, H, I)

The simulation engine is the core of OpenDT:

- **Input (F)** - Tasks and topology configuration consumed from Kafka
- **Simulation Engine (G)** - OpenDC-based power prediction
- **Output (H)** - Aggregated results written to `agg_results.parquet`
- **Topology Adjuster (I)** - The **calibrator** service that optimizes topology parameters

### Virtual Infrastructure (V)

The **Digital Twin** maintains the virtual representation of the datacenter, including the current topology and calibrated parameters.

## Detailed Design

![OpenDT Detailed Architecture](/img/design_opendt_detailed.png)

The detailed architecture expands on each component:

### Users

OpenDT supports multiple user types:

- **Students** - Learning about datacenter simulation
- **Researchers** - Conducting experiments and validating models
- **Practitioners** - Operating and optimizing real datacenters

### Frontend Components

| Component | OpenDT Implementation |
|-----------|----------------------|
| Web Interface (D) | Grafana Dashboard |
| Command Line Interface (E) | `make` commands, CLI scripts |
| API Server (F) | FastAPI-based REST API |

### Orchestration Layer

| Component | OpenDT Implementation |
|-----------|----------------------|
| Physical Orchestrator (B) | dc-mock service |
| Central Orchestrator (A) | Kafka message broker |
| Digital Orchestrator (C) | simulator + calibrator services |

### Data Platform

| Component | OpenDT Implementation |
|-----------|----------------------|
| Observable Telemetry (K) | `dc.power` Kafka topic |
| Non-Observable Telemetry (L) | Derived metrics from simulation |
| Datalake (M) | Parquet files in `data/` directory |
| Physical & Digital Twin Metadata (N) | `topology.json`, `config.yaml` |
| Twinning Log (O) | `agg_results.parquet` with timestamps |

### Simulator Components

| Component | OpenDT Implementation |
|-----------|----------------------|
| Input (G) | Task accumulator, which closes the windows |
| Simulation Engine (H) | OpenDC binary invocation |
| Output (I) | Result processor, Parquet writer |
| Topology Adjuster (J) | Calibration engine with grid search |

### Infrastructure State

**Physical Infrastructure (P1-P6)**:

| State | Description |
|-------|-------------|
| System State (P1) | Current datacenter operational status |
| SLOs (P2) | Service level objectives |
| Configuration (P3) | Hardware configuration |
| Workload (P4) | Running tasks and jobs |
| Software Stack (P5) | Installed software |
| Topology (P6) | Physical hardware layout |

**Virtual Infrastructure (V1-V6)**:

The digital twin mirrors this state, with the ability to modify parameters for what-if analysis:

| State | Description |
|-------|-------------|
| System State (V1) | Simulated operational status |
| SLOs (V2) | Target service levels |
| Configuration (V3) | Simulated configuration |
| Workload (V4) | Replayed workload |
| Software Stack (V5) | Simulated software |
| Topology (V6) | Adjustable topology with calibrated parameters |

## Data Flow
```
                      Physical Infrastructure
                               │
                               ▼
                          ┌─────────┐
                          │ dc-mock │ (placeholder for real datacenter)
                          └────┬────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
         dc.workload      dc.power        dc.topology
              │                │                │
              └────────────────┼────────────────┘
                               │
              ┌────────────────┴────────────────┐
              │                                 │
              ▼                                 ▼
      ┌─────────────┐                   ┌─────────────┐
      │  simulator  │◄── sim.topology ──│ calibrator  │
      └──────┬──────┘         ▲         └─────────────┘
             │                │
             │          ┌─────┴─────┐
             │          │    api    │ (writes the topology and sys.config)
             │          └───────────┘
             │
             ▼              ┌───────────┐     ┌───────────┐
    agg_results.parquet ──► │    api    │ ──► │  Grafana  │
                            └───────────┘     └───────────┘
```

The simulator reads `dc.workload` and `dc.topology`; the calibrator also reads `dc.power`. Besides
`agg_results.parquet`, the API reads each window's OpenDC output and the workload's `consumption.parquet`.

## Service Mapping

| Architecture Component | OpenDT Service | Docker Container |
|------------------------|----------------|------------------|
| Physical Orchestrator | dc-mock | `opendt-dc-mock` |
| Central Orchestrator | Kafka | `opendt-kafka` |
| Topic setup | kafka-init | `opendt-kafka-init` |
| Simulation Engine | simulator | `opendt-simulator` |
| Topology Adjuster | calibrator | `opendt-calibrator` |
| API Server | api | `opendt-api` |
| Web Interface | Grafana | `grafana` |

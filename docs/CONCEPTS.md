# Concepts

This document explains the core concepts, data models, and system behavior of OpenDT.

## Overview

OpenDT in its current state operates in **Shadow Mode**: it connects to a datacenter (real or mocked) and replays historical workload data through the OpenDC simulator. The system continuously compares predicted power consumption against actual measurements.

**Key capabilities:**
- Power consumption prediction based on workload patterns
- What-If analysis (e.g., "What if we upgrade CPU architecture?")
- Real-time topology calibration
- Carbon emission estimation

## Data Flow

```
Workload Data → dc-mock → Kafka → simulator → OpenDC → Results
----
Results → api → Grafana
```

1. **dc-mock** reads historical workload and power data from Parquet files
2. Messages are published to Kafka topics
3. **simulator** consumes workload messages, aggregates them into time windows, and invokes OpenDC
4. **api** queries results and serves them to Grafana

## Workload Data

### Tasks

A **Task** represents a job submitted to the datacenter. Each task requests compute resources for a specific duration.

| Field | Type | Description |
|-------|------|-------------|
| id | int | Unique identifier |
| submission_time | datetime | When the task was submitted |
| duration | int | Total duration in milliseconds |
| cpu_count | int | Number of CPU cores requested |
| cpu_capacity | float | CPU speed in MHz |
| mem_capacity | int | Memory capacity in MB |
| fragments | list | Execution profile segments |

**Physical interpretation:** A task represents a request for compute cycles:

```
Total Cycles = cpu_count × cpu_capacity × duration
```

### Fragments

A **Fragment** describes resource usage during a segment of task execution. Tasks can have varying resource usage over time (e.g., high CPU at start, low CPU during I/O).

| Field | Type | Description |
|-------|------|-------------|
| id | int | Fragment identifier |
| task_id | int | Parent task ID |
| duration | int | Segment duration in milliseconds |
| cpu_count | int | CPUs used in this segment |
| cpu_usage | float | CPU utilization value |

### Consumption

A **Consumption** record represents actual power telemetry from the datacenter.

| Field | Type | Description |
|-------|------|-------------|
| timestamp | datetime | Measurement time |
| power_draw | float | Instantaneous power in Watts |
| energy_usage | float | Accumulated energy in Joules |

## Topology

The **Topology** defines the datacenter hardware that the simulator uses to calculate power. It is hierarchical: Clusters contain Hosts, which have CPUs, Memory, and a Power Model.

### Structure

```
Topology
└── Cluster (e.g., "C01")
    └── Host
        ├── count: 277 (number of identical hosts)
        ├── CPU
        │   ├── coreCount: 16
        │   └── coreSpeed: 2100 MHz
        ├── Memory
        │   └── memorySize: 128 GB
        └── CPUPowerModel
            ├── modelType: "mse"
            ├── idlePower: 25 W
            ├── maxPower: 174 W
            └── calibrationFactor: 10.0
```

### Power Models

The **CPUPowerModel** defines how CPU utilization translates to power consumption.

| Model Type | Description |
|------------|-------------|
| mse | Mean Squared Error based model (default) |
| asymptotic | Non-linear curve with asymptotic behavior |
| linear | Linear interpolation between idle and max power |

Key parameters:
- **idlePower**: Power draw at 0% utilization (Watts)
- **maxPower**: Power draw at 100% utilization (Watts)
- **calibrationFactor**: Scaling factor for the mse model

## Time Windows

The simulator aggregates tasks into **time windows** for batch simulation.

### Window Behavior

1. Tasks are assigned to windows based on their submission timestamp
2. Windows close when a heartbeat message indicates time has progressed past the window end
3. When a window closes, all accumulated tasks are simulated

### Cumulative Simulation

OpenDT uses cumulative simulation: each window simulates all tasks from the beginning of the workload, not just tasks in that window. This ensures accurate long-running predictions.

### Heartbeats

**Heartbeat messages** are synthetic timestamps published by dc-mock to signal time progression. They enable deterministic window closing even when no tasks arrive.

## Calibration

When enabled, the **calibrator** service optimizes topology parameters by comparing simulation output against actual power measurements.

### Process

1. Calibrator runs parallel simulations with different parameter values
2. Each simulation result is compared against actual power (MAPE calculation)
3. The parameter value with lowest error is selected
4. Updated topology is published to Kafka
5. Simulator uses the calibrated topology for future windows

## Kafka Topics

OpenDT uses Kafka for inter-service communication.

| Topic | Purpose |
|-------|---------|
| dc.workload | Task submissions and heartbeats |
| dc.power | Actual power consumption telemetry |
| dc.topology | Real datacenter topology |
| sim.topology | Simulated/calibrated topology |
| sim.results | Simulation predictions |

## Output Files

### Aggregated Results

`simulator/agg_results.parquet` contains the combined simulation output:

| Column | Description |
|--------|-------------|
| timestamp | Simulation timestamp |
| power_draw | Predicted power in Watts |
| carbon_intensity | Grid carbon intensity (gCO2/kWh) |

### OpenDC Archives

Each simulation run is archived in `simulator/opendc/run_<N>/`:

```
run_1/
├── input/
│   ├── experiment.json    # OpenDC experiment config
│   ├── topology.json      # Topology used
│   ├── tasks.parquet      # Tasks simulated
│   └── fragments.parquet  # Task fragments
├── output/
│   ├── powerSource.parquet  # Power timeseries
│   ├── host.parquet         # Host-level metrics
│   └── service.parquet      # Service-level metrics
└── metadata.json          # Run metadata
```

## Pydantic Models

All data models are defined using Pydantic v2 in `libs/common/odt_common/models/`:

| Model | File | Description |
|-------|------|-------------|
| Task | task.py | Workload task |
| Fragment | fragment.py | Task execution segment |
| Consumption | consumption.py | Power measurement |
| Topology | topology.py | Datacenter topology |
| WorkloadMessage | workload_message.py | Kafka message wrapper |

Models provide:
- Runtime type validation
- JSON serialization/deserialization
- Automatic API documentation

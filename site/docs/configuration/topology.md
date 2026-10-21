---
sidebar_position: 4
---

# Topology

The topology file defines the datacenter hardware that OpenDT simulates.

## File Location

Each workload includes a `topology.json` file:

```
workload/SURF/topology.json
```

## Structure

```json
{
  "clusters": [{
    "name": "C01",
    "hosts": [{
      "name": "H01",
      "count": 277,
      "cpu": {
        "coreCount": 16,
        "coreSpeed": 2100
      },
      "memory": {
        "memorySize": 128000000
      },
      "cpuPowerModel": {
        "modelType": "mse",
        "power": 300.0,
        "idlePower": 25.0,
        "maxPower": 174.0,
        "calibrationFactor": 4
      }
    }],
    "powerSource": {
      "carbonTracePath": "/app/workload/carbon_zones/NL.parquet"
    }
  }]
}
```

## Cluster Configuration

| Field | Description |
|-------|-------------|
| name | Cluster identifier |
| hosts | List of host configurations |
| powerSource | Carbon intensity data source |

## Host Configuration

| Field | Description |
|-------|-------------|
| name | Host identifier |
| count | Number of identical hosts |
| cpu | CPU configuration |
| memory | Memory configuration |
| cpuPowerModel | Power model parameters |
| gpu | Optional GPUs per host: `count`, `coreCount`, `coreSpeed`, `memorySize` |
| gpuPowerModel | Power model of the GPUs (required with `gpu`): `modelType`, `power`, `idlePower`, `maxPower` |

## CPU Configuration

| Field | Description |
|-------|-------------|
| coreCount | Number of CPU cores per host |
| coreSpeed | CPU clock speed in MHz |

## Memory Configuration

| Field | Description |
|-------|-------------|
| memorySize | Memory per host (SURF: 128000000, shown as 128 GB on the Topology screen) |

## Power Model Configuration

| Field | Description |
|-------|-------------|
| modelType | Model type: "mse" or "asymptotic" |
| power | Nominal power (Watts, required) |
| idlePower | Power at 0% utilization (Watts) |
| maxPower | Power at 100% utilization (Watts) |
| calibrationFactor | Exponent r of the mse model, from 0 to 50: P(u) = idlePower + (maxPower - idlePower)(2u - u^r), with u the CPU utilization |
| asymUtil | Curve coefficient of the asymptotic model, from 0 to 1 |
| dvfs | Dynamic voltage and frequency scaling, asymptotic model only (default: false) |

For GPUs, `gpuPowerModel.modelType` takes OpenDC's models (e.g., "linear", "cubic"); the GPU prefabs use "cubic".

## Carbon Tracking

The `powerSource.carbonTracePath` points to a Parquet file with grid carbon intensity data over time, inside the
container (`workload/` is mounted at `/app/workload`). This enables carbon emission calculations. The CO₂ zone lever
switches among `carbon_zones/NL.parquet`, `DE.parquet`, `PL.parquet`, and `RO.parquet`.

## Editing at Runtime

The Topology screen and `PUT /api/topology` change the topology of the running twin, from the next window; see
[api](/docs/services/api). The dashboard edits the first cluster.

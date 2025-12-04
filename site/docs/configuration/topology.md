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
        "idlePower": 25.0,
        "maxPower": 174.0,
        "calibrationFactor": 10.0
      }
    }],
    "powerSource": {
      "carbonTracePath": "/app/workload/carbon.parquet"
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

## CPU Configuration

| Field | Description |
|-------|-------------|
| coreCount | Number of CPU cores per host |
| coreSpeed | CPU clock speed in MHz |

## Memory Configuration

| Field | Description |
|-------|-------------|
| memorySize | Memory capacity in bytes |

## Power Model Configuration

| Field | Description |
|-------|-------------|
| modelType | Model type: "mse", "asymptotic", or "linear" |
| idlePower | Power at 0% utilization (Watts) |
| maxPower | Power at 100% utilization (Watts) |
| calibrationFactor | Scaling factor (mse model) |
| asymUtil | Curve coefficient (asymptotic model) |

## Carbon Tracking

The `powerSource.carbonTracePath` points to a Parquet file with grid carbon intensity data over time. This enables carbon emission calculations.

---
sidebar_position: 2
---

# Installation

## Clone the Repository

```bash
git clone https://github.com/atlarge-research/opendt.git
cd opendt
```

## Setup Development Environment

Run the setup command to create a Python virtual environment and install dependencies:

```bash
make setup
```

This creates a `.venv` directory with all required Python packages.

## Verify Setup

Check that Docker can access the required images:

```bash
docker compose config
```

This validates the Docker Compose configuration without starting services.

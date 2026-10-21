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

Run the setup command to create a Python virtual environment and install dependencies (it needs
[uv](https://docs.astral.sh/uv/)):

```bash
make setup
```

This creates a `.venv` directory with all required Python packages. `make up` runs the OpenDT CLI from this environment,
so `make setup` comes first.

## Verify Setup

Check that the Docker Compose configuration is valid:

```bash
docker compose config
```

This validates the configuration without starting services; before the first `make up`, it warns that `RUN_ID` is not
set, which is expected.

## GitHub Codespaces

The repository also opens in GitHub Codespaces (`.devcontainer/`): the Codespace has Python 3.11 and Java 21, installs
uv, runs `make setup`, and registers the Jupyter kernel "OpenDT (.venv)" for the
[tutorial](https://github.com/atlarge-research/opendt/tree/master/tutorial).

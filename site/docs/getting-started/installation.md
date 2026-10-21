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

```bash
make setup
```

`make setup` uses uv to create `.venv` and install the Python packages. `make up` runs the OpenDT CLI from there, so
`make setup` comes first.

## GitHub Codespaces

The repository also opens in GitHub Codespaces (`.devcontainer/`), with Python 3.11 and Java 21. The Codespace installs
uv, runs `make setup`, and registers the Jupyter kernel "OpenDT (.venv)" for the
[tutorial](https://github.com/atlarge-research/opendt/tree/master/tutorial).

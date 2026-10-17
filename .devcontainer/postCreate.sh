#!/usr/bin/env bash
# Prepare a Codespace for the OpenDT tutorial: the project's Python environment and a Jupyter kernel.
set -euo pipefail
cd "$(dirname "$0")/.."

curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
make setup
.venv/bin/python -m ipykernel install --user --name opendt --display-name "OpenDT (.venv)"
.venv/bin/python -c "import sys; sys.path.insert(0, 'tutorial'); import opendt_tutorial; opendt_tutorial.check_setup()"

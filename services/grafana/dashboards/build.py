"""Writes the dashboards into the provisioning folder: python3 services/grafana/dashboards/build.py"""

import json
from pathlib import Path

from screens import detailed, topology, tutorial

OUT = Path(__file__).resolve().parents[1] / "provisioning" / "dashboards"
DASHBOARDS = {
    "overview.json": detailed,
    "topology.json": topology,
    "tutorial.json": tutorial,
}


def write(out=OUT):
    for path, board in DASHBOARDS.items():
        (out / path).write_text(json.dumps(board, indent=4, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    write()

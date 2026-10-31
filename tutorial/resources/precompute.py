"""Run once every simulation of the notebooks, and those their explore prompts suggest, and keep
them in resources/results/: the notebooks then answer at once, without Java or OpenDC.

After a change to OpenDC, the SURF trace, or a notebook's simulations, from the repository root:
python tutorial/resources/precompute.py
"""

import dataclasses
import shutil
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the tutorial folder, for `resources`
from resources import CARBON_ZONES, GREENEST_ZONE, TRACE_END, TRACE_START, sim  # noqa: E402

DAY = TRACE_START + pd.Timedelta("24h")
RUNS = [
    # notebook 1: the first day with 1/4 to 10x the hosts (and 160 to 1,000 to explore)
    *((DAY, {"hosts": hosts}) for hosts in (69, 138, 160, 200, 277, 500, 1000, 2770)),
    # notebook 2: the week with r from 1 to 20, 30, and 40
    *((TRACE_END, {"r": r}) for r in (*range(1, 21), 30, 40)),
    # notebook 3: the week in each country, and with fewer hosts in RO (138, 161, 200) and NL (200)
    *((TRACE_END, {"carbon": zone}) for zone in (*CARBON_ZONES, GREENEST_ZONE)),
    *(
        (TRACE_END, {"hosts": h, "carbon": z})
        for h, z in ((138, "RO"), (161, "RO"), (200, "RO"), (200, "NL"))
    ),
]

if __name__ == "__main__":
    shutil.rmtree(sim.PATHS.results, ignore_errors=True)
    sim.PATHS = dataclasses.replace(sim.PATHS, output=sim.PATHS.results)  # each run lands there
    for until, params in RUNS:
        print(sim.simulate(until, **params))

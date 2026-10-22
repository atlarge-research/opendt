"""Derive workload/SURF/carbon_zones/ from the Electricity Maps traces in opendc-traces.

Usage:
    python tutorial/resources/make_carbon_subset.py ~/Atlarge/opendc-traces/carbon/traces workload/SURF/carbon_zones

Source files are `<ZONE>_2021-2024.parquet` (hourly, Electricity Maps, ODbL 1.0). The tutorial keeps
October 2022 only (the SURF trace runs 2022-10-06 22:00 to 2022-10-13 22:00 UTC) in the schema OpenDC
expects: timestamp[ms] (UTC, no zone) and carbon_intensity [gCO2/kWh], both non-null.
"""

import sys
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ZONES = ("NL", "DE", "RO", "PL", "SE")
START, END = pd.Timestamp("2022-10-01 00:00"), pd.Timestamp("2022-11-01 00:00")
SCHEMA = pa.schema(
    [
        pa.field("timestamp", pa.timestamp("ms"), nullable=False),
        pa.field("carbon_intensity", pa.float64(), nullable=False),
    ]
)


def main(source: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for zone in ZONES:
        df = pd.read_parquet(source / f"{zone}_2021-2024.parquet")
        ts = df["timestamp"]  # naive UTC, timestamp[ms]
        keep = (ts >= START) & (ts < END)
        table = pa.table(
            {"timestamp": ts[keep], "carbon_intensity": df.loc[keep, "carbon_intensity"]},
            schema=SCHEMA,
        )
        pq.write_table(table, out / f"{zone}.parquet")
        print(f"{zone}: {table.num_rows} rows")


if __name__ == "__main__":
    main(Path(sys.argv[1]).expanduser(), Path(sys.argv[2]))

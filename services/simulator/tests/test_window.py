"""A window runs OpenDC on the tasks so far, and reuses the run before it while nothing has changed."""

import json
from datetime import UTC, datetime, timedelta

import pandas as pd
from odt_common import ResultCache, TaskAccumulator, Topology
from odt_common.models import Task
from odt_common.result_cache import HORIZON
from simulator.main import SimulationService
from simulator.result_processor import SimulationResultProcessor

T0 = datetime(2022, 10, 6, 22, tzinfo=UTC)


class OpenDC:
    """Writes a run as OpenDC would: 10 kW every 30 s, from the trace's start to an hour past the
    window's end (odc_runner's HORIZON)."""

    runs = 0

    def run_simulation(self, run_dir, simulated_time, **_):
        self.runs += 1
        times = pd.date_range(T0, simulated_time + HORIZON, freq="30s")
        out = run_dir / "output/now/raw-output/0/seed=0"
        out.mkdir(parents=True)
        power = {"power_draw": 10000.0, "energy_usage": 1.0, "carbon_intensity": 1.0}
        pd.DataFrame(
            {
                "timestamp_absolute": times.as_unit("ms").astype("int64"),
                **power,
                "carbon_emission": 1.0,
            }
        ).to_parquet(out / "powerSource.parquet")
        (run_dir / "metadata.json").write_text(json.dumps({"simulated_time": str(simulated_time)}))
        return True, run_dir / "output"


def service(tmp_path):
    """A simulator without Kafka, with one task."""
    s = SimulationService.__new__(SimulationService)
    s.task_accumulator = TaskAccumulator()
    s.result_cache = ResultCache()
    s.opendc_runner = OpenDC()
    s.simulation_frequency = timedelta(minutes=5)
    s.run_number = 0
    s.scheduler = None
    s.simulated_topology = Topology.model_construct(clusters=[])
    s.output_base_dir = tmp_path
    s.result_processor = SimulationResultProcessor(tmp_path)
    task = {"duration": 1000, "cpu_count": 1, "cpu_capacity": 1000.0, "mem_capacity": 100}
    s.task_accumulator.add_task(Task(id=1, submission_time=T0, **task))
    return s


def test_reuses_the_run_before(tmp_path):
    s = service(tmp_path)
    s._run_simulation()
    s._run_simulation()
    assert s.opendc_runner.runs == 1
    metadata = json.loads((tmp_path / "opendc/run_2/metadata.json").read_text())
    assert metadata["cached"] and metadata["simulated_time"] == "2022-10-06T22:10:00+00:00"
    power = pd.read_parquet(tmp_path / "agg_results.parquet")
    assert power["timestamp"].max() == T0 + timedelta(minutes=10) and power["cached"].tolist()[-1]

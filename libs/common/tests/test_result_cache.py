"""A reused run is copied without its metadata.json, which marks a run complete for its readers; a
run is reused only up to the HORIZON it simulated."""

from datetime import UTC, datetime, timedelta

from odt_common import ResultCache, Topology


def test_copy_skips_metadata(tmp_path):
    cached, new = tmp_path / "run_1", tmp_path / "run_2"
    (cached / "output").mkdir(parents=True)
    (cached / "output" / "host.parquet").write_text("results")
    (cached / "metadata.json").write_text('{"simulated_time": "2022-10-06T22:05:00+00:00"}')
    ResultCache().copy_to_new_run(cached, new)
    assert (new / "output" / "host.parquet").read_text() == "results"
    assert not (new / "metadata.json").exists()


def test_reused_within_the_hour(tmp_path):
    cache, t = ResultCache(), datetime(2022, 10, 6, 22, tzinfo=UTC)
    topology = Topology.model_construct(clusters=[])
    cache.update(topology, None, 10, t, tmp_path)
    assert cache.can_reuse(topology, None, 10, t + timedelta(minutes=55))
    assert not cache.can_reuse(topology, None, 10, t + timedelta(hours=1))
    assert not cache.can_reuse(topology, None, 11, t + timedelta(minutes=5))

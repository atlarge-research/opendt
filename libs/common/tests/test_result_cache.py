"""A reused run is copied without its metadata.json, which marks a run complete for its readers."""

from odt_common import ResultCache


def test_copy_skips_metadata(tmp_path):
    cached, new = tmp_path / "run_1", tmp_path / "run_2"
    (cached / "output").mkdir(parents=True)
    (cached / "output" / "host.parquet").write_text("results")
    (cached / "metadata.json").write_text('{"simulated_time": "2022-10-06T22:05:00+00:00"}')
    ResultCache().copy_to_new_run(cached, new)
    assert (new / "output" / "host.parquet").read_text() == "results"
    assert not (new / "metadata.json").exists()

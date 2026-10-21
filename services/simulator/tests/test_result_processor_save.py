"""The aggregated results are replaced whole, so a reader never sees half a file."""

import pandas as pd
from simulator.result_processor import save


def test_save_replaces_whole(tmp_path):
    path = tmp_path / "agg_results.parquet"
    save(pd.DataFrame({"a": [1]}), path)
    save(pd.DataFrame({"a": [1, 2]}), path)
    assert pd.read_parquet(path)["a"].tolist() == [1, 2]
    assert [p.name for p in tmp_path.iterdir()] == ["agg_results.parquet"]

"""The portfolio: CPUs, GPUs, and racks, preconfigured or the user's own, kept in the data folder across runs."""

import json

import pytest
from api import portfolio


@pytest.fixture(autouse=True)
def data(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))


def test_presets():
    racks = portfolio.parts("Rack")
    assert racks["SURF-SARA"]["hosts"] == 277
    assert all(rack["cpu"] in portfolio.parts("CPU") for rack in racks.values())


def test_new_from_first_preset():
    # the table starts a new row's numbers at 0: what it leaves out, it takes from the first preset
    portfolio.save(
        "CPU", None, {"name": "Future", "cores": 256, "ghz": 0, "idle_w": 0, "max_w": 400}
    )
    assert portfolio.parts("CPU")["Future"] == {
        "cores": 256,
        "ghz": 2.1,
        "idle_w": 25,
        "max_w": 400,
        "from": "Yours",
    }


def test_preset_stays():
    portfolio.save("CPU", "SURF-SARA", {"name": "SURF-SARA", "idle_w": 10})
    cpus = portfolio.parts("CPU")
    assert (cpus["SURF-SARA"]["idle_w"], cpus["SURF-SARA (yours)"]["idle_w"]) == (25, 10)


def test_rename_and_remove():
    portfolio.save("GPU", None, {"name": "Mine"})
    portfolio.save("GPU", "Mine", {"name": "Ours", "cores": 1000})
    assert "Mine" not in portfolio.parts("GPU") and portfolio.parts("GPU")["Ours"]["cores"] == 1000
    portfolio.remove("GPU", "Ours")
    portfolio.remove("GPU", "A100 40 GiB")  # a preset stays
    assert list(portfolio.parts("GPU")) == ["A100 40 GiB"]


def test_kept_in_the_data_folder(tmp_path):
    portfolio.save("Rack", None, {"name": "Edge", "cpu": "Xeon E-2288G", "hosts": 10})
    assert json.loads((tmp_path / "portfolio.json").read_text())["Rack"]["Edge"]["hosts"] == 10


def test_rack_of_known_parts():
    with pytest.raises(ValueError):
        portfolio.save("Rack", None, {"name": "X", "cpu": "Nope"})
    portfolio.save(
        "Rack", None, {"name": "GPUs", "gpu": "A100 40 GiB"}
    )  # one GPU per host, until a count
    assert portfolio.parts("Rack")["GPUs"]["gpus"] == 1

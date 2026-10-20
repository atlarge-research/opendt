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


def test_new_from_the_first():
    # the table starts a new row's numbers at 0: what it leaves out, it takes from the first part
    portfolio.save(
        "CPU", None, {"name": "Future", "cores": 256, "ghz": 0, "idle_w": 0, "max_w": 400}
    )
    assert portfolio.parts("CPU")["Future"] == {
        "cores": 256,
        "ghz": 2.1,
        "idle_w": 25,
        "max_w": 400,
    }


def test_edited_in_place():
    portfolio.save("CPU", "SURF-SARA", {"name": "SURF-SARA", "idle_w": 10})
    assert portfolio.parts("CPU")["SURF-SARA"]["idle_w"] == 10
    assert (
        portfolio.PRESETS["CPU"]["SURF-SARA"]["idle_w"] == 25
    )  # without portfolio.json, as shipped


def test_rename_and_remove():
    portfolio.save("GPU", None, {"name": "Mine"})
    portfolio.save("GPU", "Mine", {"name": "Ours", "cores": 1000})
    assert list(portfolio.parts("GPU")) == ["A100 40 GiB", "Ours"]
    portfolio.remove("GPU", "Ours")
    portfolio.remove("GPU", "A100 40 GiB")
    portfolio.save(
        "GPU", None, {"name": "Again"}
    )  # with none left, a copy of the first preconfigured one
    assert portfolio.parts("GPU") == {"Again": portfolio.PRESETS["GPU"]["A100 40 GiB"]}


def test_kept_in_the_data_folder(tmp_path):
    portfolio.save("Rack", None, {"name": "Edge", "cpu": "Xeon E-2288G", "hosts": 10})
    assert json.loads((tmp_path / "portfolio.json").read_text())["Rack"]["Edge"]["hosts"] == 10
    (tmp_path / "portfolio.json").unlink()
    assert portfolio.parts("Rack") == portfolio.PRESETS["Rack"]


def test_rack_of_known_parts():
    with pytest.raises(ValueError):
        portfolio.save("Rack", None, {"name": "X", "cpu": "Nope"})
    portfolio.save(
        "Rack", None, {"name": "GPUs", "gpu": "A100 40 GiB"}
    )  # one GPU per host, until a count
    assert portfolio.parts("Rack")["GPUs"]["gpus"] == 1

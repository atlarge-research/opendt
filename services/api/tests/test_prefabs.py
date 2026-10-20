"""The prefabs: CPUs, GPUs, and racks, as shipped, then the user's, kept in the data folder across runs."""

import json

import pytest
from api import prefabs


@pytest.fixture(autouse=True)
def data(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))


def test_shipped():
    racks = prefabs.parts("Rack")
    assert racks["SURF-SARA"]["hosts"] == 277
    assert all(rack["cpu"] in prefabs.parts("CPU") for rack in racks.values())


def test_new_from_the_first():
    # the table starts a new row's numbers at 0: what it leaves out, it takes from the first part
    prefabs.save("CPU", None, {"name": "Future", "cores": 256, "ghz": 0, "idle_w": 0, "max_w": 400})
    assert prefabs.parts("CPU")["Future"] == {
        "cores": 256,
        "ghz": 2.1,
        "idle_w": 25,
        "max_w": 400,
    }


def test_edited_in_place():
    prefabs.save("CPU", "SURF-SARA", {"name": "SURF-SARA", "idle_w": 10})
    assert prefabs.parts("CPU")["SURF-SARA"]["idle_w"] == 10
    assert prefabs.SHIPPED["CPU"]["SURF-SARA"]["idle_w"] == 25  # without prefabs.json, as shipped


def test_rename_and_remove():
    prefabs.save("GPU", None, {"name": "Mine"})
    prefabs.save("GPU", "Mine", {"name": "Ours", "cores": 1000})
    assert list(prefabs.parts("GPU")) == ["A100 40 GiB", "Ours"]
    prefabs.remove("GPU", "Ours")
    prefabs.remove("GPU", "A100 40 GiB")
    prefabs.save("GPU", None, {"name": "Again"})  # with none left, a copy of the first shipped
    assert prefabs.parts("GPU") == {"Again": prefabs.SHIPPED["GPU"]["A100 40 GiB"]}


def test_kept_in_the_data_folder(tmp_path):
    prefabs.save("Rack", None, {"name": "Edge", "cpu": "Xeon E-2288G", "hosts": 10})
    assert json.loads((tmp_path / "prefabs.json").read_text())["Rack"]["Edge"]["hosts"] == 10
    (tmp_path / "prefabs.json").unlink()
    assert prefabs.parts("Rack") == prefabs.SHIPPED["Rack"]


def test_rack_of_known_parts():
    with pytest.raises(ValueError):
        prefabs.save("Rack", None, {"name": "X", "cpu": "Nope"})
    prefabs.save(
        "Rack", None, {"name": "GPUs", "gpu": "A100 40 GiB"}
    )  # one GPU per host, until a count
    assert prefabs.parts("Rack")["GPUs"]["gpus"] == 1

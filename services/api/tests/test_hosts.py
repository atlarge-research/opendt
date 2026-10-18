"""The Topology table: host groups as rows, edited in place, with CPUs and GPUs from prefabs or custom."""

from api import hosts

H01 = {
    "name": "H01",
    "count": 277,
    "cpu": {"coreCount": 16, "coreSpeed": 2100.0},
    "memory": {"memorySize": 128_000_000},
    "cpuPowerModel": {
        "modelType": "mse",
        "power": 300.0,
        "idlePower": 25.0,
        "maxPower": 174.0,
        "calibrationFactor": 4.0,
    },
}


def test_row():
    assert hosts.row(1, H01) == {
        "id": 1,
        "kind": "SURF-SARA",
        "count": 277,
        "cpu": "SURF-SARA",
        "cores": 16,
        "ghz": 2.1,
        "memory_gb": 128,
        "gpu": "None",
        "gpus": 0,
        "idle_w": 25,
        "max_w": 174,
    }


def test_count():
    [h01] = hosts.edit([H01], hosts.Row(id=1, kind="SURF-SARA", count=138))
    assert h01 == {**H01, "count": 138}  # the rest as it was, its name too


def test_custom_cpu():
    [h01] = hosts.edit([H01], hosts.Row(id=1, cpu="SURF-SARA", cores=32))
    assert h01["cpu"]["coreCount"] == 32
    assert hosts.row(1, h01)["cpu"] == "Custom"


def test_cpu_prefab():
    [epyc] = hosts.edit([H01], hosts.Row(id=1, cpu="2x EPYC 7502", cores=16))
    assert (epyc["cpu"], epyc["cpuPowerModel"]["idlePower"]) == (
        {"coreCount": 64, "coreSpeed": 3200.0},
        120,
    )


def test_gpus():
    [gpu] = hosts.edit([H01], hosts.Row(id=1, gpu="A100 40 GiB", gpus=4))
    assert gpu["gpu"]["count"] == 4
    assert gpu["gpuPowerModel"] == {
        "modelType": "cubic",
        "power": 400,
        "idlePower": 100,
        "maxPower": 400,
    }
    assert (hosts.row(1, gpu)["gpu"], hosts.row(1, gpu)["gpus"]) == ("A100 40 GiB", 4)
    [h01] = hosts.edit([gpu], hosts.Row(id=1, gpu="None"))
    assert "gpu" not in h01 and "gpuPowerModel" not in h01


def test_add():
    row = hosts.Row(kind="Edge", count=10, cpu="Xeon E-2288G", memory_gb=32)
    _, edge = hosts.edit([H01], row)
    assert (edge["name"], edge["count"], edge["cpu"]["coreCount"]) == ("Edge", 10, 8)


def test_new_row_zeros():
    # the table starts a new row's numbers at 0: what it leaves out, it takes from the first group
    row = hosts.Row(count=0, cpu="", cores=0, ghz=0, memory_gb=0, idle_w=0, max_w=0, gpus=0)
    _, new = hosts.edit([H01], row)
    assert (new["name"], new["count"], new["cpu"], new["cpuPowerModel"]["idlePower"]) == (
        "New",
        1,
        H01["cpu"],
        25,
    )


def test_new_row_without_gpus():
    [gpu] = hosts.edit([H01], hosts.Row(id=1, gpu="A100 40 GiB", gpus=4))
    _, new = hosts.edit([gpu], hosts.Row(kind="CPU only", count=5))
    assert "gpu" not in new


def test_delete():
    edge = {**H01, "name": "Edge"}
    assert hosts.edit([H01, edge], hosts.Row(id=2, count=0)) == [H01]
    assert hosts.edit([H01], hosts.Row(id=1, count=0)) == []  # the topology refuses it


def test_summary():
    # as the decisions name a group: a change of GPUs is a decision too
    [gpu] = hosts.edit([H01], hosts.Row(id=1, gpu="A100 40 GiB", gpus=4))
    assert (hosts.summary(H01), hosts.summary(gpu)) == ("277 SURF-SARA", "277 SURF-SARA with 4 GPUs each")

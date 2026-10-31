"""The tutorial's config (the default) and its topology are valid OpenDT inputs."""

import json

from conftest import REPO, TUTORIAL_DIR
from odt_common.config import AppConfig
from odt_common.models import Topology

CONFIGS = TUTORIAL_DIR / "resources/configs"


def test_config_runs_fast_without_calibration():
    config = AppConfig.load(REPO / "config/default.yaml")
    services = config.services
    assert config.global_config.speed_factor == -1 and not config.calibration_enabled
    assert (
        services.dc_mock.heartbeat_frequency_minutes
        <= services.simulator.simulation_frequency_minutes
    )


def test_calibration_config_searches_r_from_3_to_9():
    calibrator = AppConfig.load(REPO / "config/default.yaml").services.calibrator
    assert calibrator.calibrated_property == "cpuPowerModel.calibrationFactor"
    assert (calibrator.min_value, calibrator.max_value, calibrator.linspace_points) == (3, 9, 7)


def test_topology_for_the_demo_is_surf_with_2770_hosts():
    surf = json.loads((REPO / "workload/SURF/topology.json").read_text())
    demo = json.loads((CONFIGS / "topology_2770_hosts.json").read_text())
    surf["clusters"][0]["hosts"][0]["count"] = 2770
    assert demo == surf and Topology(**demo).total_host_count() == 2770

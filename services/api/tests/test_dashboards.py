"""The provisioned Grafana dashboards ask the API only for what it serves."""

import json
import re
from pathlib import Path
from urllib.parse import urlparse

import pytest
from api import main, twin

REPO = Path(__file__).resolve().parents[3]
DASHBOARDS = REPO / "services" / "grafana" / "provisioning" / "dashboards"
ROUTES = {(method, route.path) for route in main.app.routes for method in route.methods}


def queries(dashboard):
    """(title, host it should call, url, method) of each request of a dashboard: the Grafana server reaches the
    API inside Docker, while the control panel sends its requests from the browser, to the host port."""
    for panel in dashboard["panels"]:
        if panel["type"] == "volkovlabs-form-panel":
            for r in (panel["options"]["initial"], panel["options"]["update"]):
                yield panel["title"], "localhost:3001", r["url"], r["method"]
        for t in panel.get("targets", []):  # a row has none
            yield panel["title"], "api:8000", t["url"], t["url_options"]["method"]
    for marker in dashboard["annotations"]["list"]:
        if "target" in marker:  # not Grafana's own annotations
            target = marker["target"]
            yield marker["name"], "api:8000", target["url"], target["url_options"]["method"]


@pytest.mark.parametrize("dashboard", sorted(DASHBOARDS.glob("*.json")), ids=lambda path: path.name)
def test_panels_call_api_routes(dashboard):
    for title, host, url, method in queries(json.loads(dashboard.read_text())):
        url = urlparse(url)
        assert url.netloc == host and (method, url.path) in ROUTES, (title, method, url.path)


def test_graphs_mark_topology_changes():
    markers = json.loads((DASHBOARDS / "overview.json").read_text())["annotations"]["list"]
    assert [m["target"]["url"] for m in markers] == ["http://api:8000/api/events"]


def test_control_panel_offers_the_carbon_zones_of_the_api():
    panels = json.loads((DASHBOARDS / "overview.json").read_text())["panels"]
    [form] = [p for p in panels if p["type"] == "volkovlabs-form-panel"]
    [zones] = [e for e in form["options"]["elements"] if e["id"] == "carbon_zone"]
    assert [o["value"] for o in zones["options"]] == list(twin.CARBON_TRACES)


def test_home_dashboard_is_provisioned():
    compose = (REPO / "docker-compose.yml").read_text()
    home = re.search(r"DEFAULT_HOME_DASHBOARD_PATH=\S+/(\S+\.json)", compose).group(1)
    assert (DASHBOARDS / home).exists()

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


def requests(panel):
    """The host a panel should call, and the (host, method, path) of each of its requests: the Grafana server
    reaches the API inside Docker, while the form panel sends its requests from the browser, to the host port."""
    if panel["type"] == "volkovlabs-form-panel":
        host, sent = "localhost:3001", [panel["options"]["initial"], panel["options"]["update"]]
        found = [(r["url"], r["method"]) for r in sent]
    else:
        host, found = "api:8000", [(t["url"], t["url_options"]["method"]) for t in panel["targets"]]
    return host, [(urlparse(url).netloc, method, urlparse(url).path) for url, method in found]


@pytest.mark.parametrize("dashboard", sorted(DASHBOARDS.glob("*.json")), ids=lambda path: path.name)
def test_panels_call_api_routes(dashboard):
    for panel in json.loads(dashboard.read_text())["panels"]:
        host, found = requests(panel)
        for netloc, method, path in found:
            assert netloc == host and (method, path) in ROUTES, (panel["title"], method, path)


def test_control_panel_offers_the_carbon_zones_of_the_api():
    panels = json.loads((DASHBOARDS / "overview.json").read_text())["panels"]
    [form] = [p for p in panels if p["type"] == "volkovlabs-form-panel"]
    [zones] = [e for e in form["options"]["elements"] if e["id"] == "carbon_zone"]
    assert [o["value"] for o in zones["options"]] == list(twin.CARBON_TRACES)


def test_home_dashboard_is_provisioned():
    compose = (REPO / "docker-compose.yml").read_text()
    home = re.search(r"DEFAULT_HOME_DASHBOARD_PATH=\S+/(\S+\.json)", compose).group(1)
    assert (DASHBOARDS / home).exists()

"""The provisioned Grafana dashboards ask the API only for what it serves."""

import json
import re
from pathlib import Path
from typing import get_args
from urllib.parse import urlparse

import pytest
from api import main, twin

REPO = Path(__file__).resolve().parents[3]
DASHBOARDS = REPO / "services" / "grafana" / "provisioning" / "dashboards"
ROUTES = {(method, route.path) for route in main.app.routes for method in route.methods}


OURS = [
    "overview.json",
    "simple.json",
    "topology.json",
]  # Grafana's v2 format; the classic one is v1


def load(name):
    return json.loads((DASHBOARDS / name).read_text())


def panels(board):
    """(title, type, options, targets) of each panel, in Grafana's classic or v2 format."""
    if "spec" not in board:
        return [
            (p["title"], p["type"], p.get("options", {}), p.get("targets", []))
            for p in board["panels"]
        ]
    return [
        (
            e["spec"]["title"],
            e["spec"]["vizConfig"]["group"],
            e["spec"]["vizConfig"]["spec"]["options"],
            [q["spec"]["query"]["spec"] for q in e["spec"]["data"]["spec"]["queries"]],
        )
        for e in board["spec"]["elements"].values()
    ]


def markers(board):
    """The queries of the annotations, without Grafana's own."""
    if "spec" not in board:
        return [m["target"] for m in board["annotations"]["list"] if "target" in m]
    return [
        a["spec"]["query"]["spec"]
        for a in board["spec"]["annotations"]
        if a["spec"]["query"]["group"] != "grafana"
    ]


def queries(board):
    """(title, host it should call, url, method) of each request of a dashboard: the Grafana server reaches the
    API inside Docker, while the forms send their requests from the browser, to the host port."""
    for title, kind, options, targets in panels(board):
        if kind == "volkovlabs-form-panel":
            for key in ("initial", "update"):
                request = options.get(key, {})
                if "url" in request:  # not custom code, as the plot picker's
                    yield title, "localhost:3001", request["url"], request["method"]
        for t in targets:
            yield title, "api:8000", t["url"], t["url_options"]["method"]
    for target in markers(board):
        yield "markers", "api:8000", target["url"], target["url_options"]["method"]


@pytest.mark.parametrize("dashboard", sorted(DASHBOARDS.glob("*.json")), ids=lambda path: path.name)
def test_panels_call_api_routes(dashboard):
    for title, host, url, method in queries(json.loads(dashboard.read_text())):
        url = urlparse(url)
        assert url.netloc == host and (method, url.path) in ROUTES, (title, method, url.path)


@pytest.mark.parametrize("name", OURS)
def test_graphs_mark_topology_changes(name):
    assert [m["url"] for m in markers(load(name))] == ["http://api:8000/api/events"]


@pytest.mark.parametrize(
    ("field", "api"),
    [
        ("carbon_zone", list(twin.CARBON_TRACES)),
        ("kind_1", list(twin.SERVERS)),
        ("scheduler", list(get_args(main.SCHEDULERS))),
    ],
)
def test_forms_offer_what_the_api_takes(field, api):
    elements = [
        e
        for name in OURS
        for _, kind, options, _ in panels(load(name))
        if kind == "volkovlabs-form-panel"
        for e in options.get("elements", [])
    ]
    [offered, *same] = [[o["value"] for o in e["options"]] for e in elements if e["id"] == field]
    assert offered == api and all(other == offered for other in same)


def test_every_plot_can_be_picked_and_shown():
    spec = load("overview.json")["spec"]
    [plots] = [v["spec"] for v in spec["variables"] if v["spec"]["name"] == "plots"]
    picker = spec["elements"]["layout"]["spec"]["vizConfig"]["spec"]["options"]["elements"][0]
    shown = [
        item["spec"]["element"]["name"]
        for row in spec["layout"]["spec"]["rows"]
        if row["spec"]["layout"]["kind"] == "AutoGridLayout"
        for item in row["spec"]["layout"]["spec"]["items"]
    ]
    assert plots["query"].split(",") == [o["value"] for o in picker["options"]] == shown


def test_home_page_is_a_provisioned_dashboard():
    compose = (REPO / "docker-compose.yml").read_text()
    home = re.search(r"GF_USERS_HOME_PAGE=/d/(\S+)", compose).group(1)
    assert home in [load(name)["metadata"]["name"] for name in OURS]

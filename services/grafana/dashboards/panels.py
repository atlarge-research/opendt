"""The building blocks of every screen: the API's endpoints, the colours, and Grafana's panel types."""

import re

DS = {"type": "yesoreyeram-infinity-datasource", "uid": "df5tfgbpfeakgc"}
API = "http://api:8000"  # from the Grafana server
BROWSER_API = "http://localhost:3001"  # from the browser, for the forms
CLUSTER, RANGE = f"{API}/api/cluster", "?start=${__from:date:iso}&end=${__to:date:iso}"
POWER = f"{API}/api/power?interval_seconds=60"
CO2 = f"{API}/api/co2_emission?interval_seconds=60"
ACCURACY, STATUS = f"{API}/api/accuracy", f"{API}/api/status"
PERIODS = ["minute", "hour", "day", "week", "month", "year"]
WEEK = {"from": "2022-10-06T22:00:00.000Z", "to": "2022-10-13T22:00:00.000Z"}  # the SURF week

# the paper's colours (reproducibility-capsule/plots/config.py), each with a meaning: grey measured, green good
# (OpenDT, work done), blue neutral, yellow a warning, orange bad-ish, red bad
GREY, GREEN, BLUE = "#999999", "#009E73", "#338ec1"
YELLOW, ORANGE, RED = "#F0E442", "#E69F00", "#D55E00"
MARKERS = "rgba(255, 255, 255, 0.35)"  # light, so the data stays in front
BOX = "#22252b"  # Grafana's dark secondary background: a box in a panel
TEXT = {"titleSize": 12, "valueSize": 22}  # the same in every tile and box
TIME = ("timestamp", "timestamp", "timestamp")
BARS = {"drawStyle": "bars", "fillOpacity": 80, "barAlignment": 1}  # a bar from each period's start
DASHED = {"fill": "dash", "dash": [8, 4]}


def column(selector, name, kind="number"):
    return {"selector": selector, "text": name, "type": kind}


def target(url, columns, computed=()):
    """A query of an API table: (selector, name[, type]) per column, (expression, name) per computed one."""
    query = {
        "refId": "A",
        "type": "json",
        "source": "url",
        "parser": "backend",
        "format": "table",
        "url": url,
        "url_options": {"method": "GET"},
        "root_selector": "data",
        "columns": [column(*c) for c in columns],
    }
    if computed:
        query["computed_columns"] = [column(*c) for c in computed]
    return query


def override(name, **props):
    return {
        "matcher": {"id": "byName", "options": name},
        "properties": [{"id": k.replace("__", "."), "value": v} for k, v in props.items()],
    }


def units(unit, *names, **props):
    return [override(name, unit=unit, **props) for name in names]


def organize(order, hide=()):
    """Fields in this order (the backend parser sorts them by name), without those only computed from."""
    options = {"indexByName": {name: i for i, name in enumerate(order)}}
    if hide:
        options["excludeByName"] = dict.fromkeys(hide, True)
    return {"id": "organize", "options": options}


def better_axis(direction):
    """A flat, invisible line on the right axis, only for its label: BETTER and an arrow."""
    return {
        "custom__axisPlacement": "right",
        # the label reads top to bottom: ← points up, → down
        "custom__axisLabel": "BETTER ←" if direction == "higher" else "BETTER →",
        "custom__lineWidth": 0,
        "custom__axisGridShow": False,
        "custom__hideFrom": {"legend": True, "tooltip": True, "viz": False},
        "mappings": [
            {"type": "range", "options": {"from": -1e12, "to": 1e12, "result": {"text": " "}}}
        ],
    }


def timeseries(
    title,
    url,
    axis,
    colors,
    columns,
    better=None,
    unit=None,
    computed=(),
    hide=(),
    right=None,
    gaps=False,
    decimals=1,
    apart=(),
    signed=False,
    **custom,
):
    """A time series of an API table. `colors` maps each shown field to its colour, in legend order. The
    legend gives each line its axis' unit and latest value (with `gaps`, the latest there is); `apart`
    lines are dashed (bars: lighter), to tell them apart in grayscale. `right` is (field, label) of a
    second axis; `better` ("higher" or "lower") labels the right axis; a `signed` axis goes below 0."""

    def named(name):  # a percentage shows its own %
        found = re.search(r"\[.+\]$", right[1] if right and name == right[0] else axis)
        return f"{name} {found.group()}" if found and unit != "percentunit" else name

    names = {name: named(name) for name in colors}
    columns = [(c[0], names.get(c[1], c[1]), *c[2:]) for c in columns]
    computed = [(e, names.get(n, n)) for e, n in computed]
    custom = {"axisLabel": axis, "lineWidth": 2, "showPoints": "never", **custom}
    if signed:
        custom |= {"axisSoftMin": 0, "axisSoftMax": 0}  # the axis still shows 0
    defaults = ({} if signed else {"min": 0}) | {"decimals": decimals, "custom": custom}
    defaults |= {"unit": unit} if unit else {}
    overrides = {names[n]: {"color": {"mode": "fixed", "fixedColor": c}} for n, c in colors.items()}
    for name in apart:
        bars = custom.get("drawStyle") == "bars"
        overrides[names[name]] |= (
            {"custom__fillOpacity": 35} if bars else {"custom__lineStyle": DASHED}
        )
    if right:
        overrides[names[right[0]]] |= {
            "custom__axisPlacement": "right",
            "custom__axisLabel": right[1],
        }
    if better:
        computed = [*computed, ("0", "better")]
        overrides["better"] = better_axis(better)
    overrides["timestamp"] = {"custom__axisLabel": "Simulated time [UTC]"}
    return {
        "type": "timeseries",
        "title": title,
        "targets": [target(url, [TIME, *columns], computed)],
        "transformations": [organize([*names.values(), *(["better"] if better else [])], hide)],
        "fieldConfig": {
            "defaults": defaults,
            "overrides": [override(n, **p) for n, p in overrides.items()],
        },
        "options": {
            "legend": {"calcs": ["lastNotNull" if gaps else "last"]},
            "tooltip": {"mode": "multi"},
        },
    }


def stat(
    title,
    url,
    columns,
    overrides=(),
    computed=(),
    root="data",
    hide=(),
    more=(),
    orientation="auto",
    unit=None,
    decimals=None,
):
    """The latest values of an API table (and of the `more` queries), one box each, the name over the value;
    `unit` and `decimals` for all of them, `overrides` for the others."""
    queries = [target(url, columns, computed) | {"root_selector": root}, *more]
    for i, query in enumerate(queries):
        query["refId"] = "ABCDEF"[i]
    names = [c["text"] for q in queries for c in q["columns"] + q.get("computed_columns", [])]
    # one table first: the order applies to one table only, and the names keep no query letter
    merge = [{"id": "concatenate", "options": {"frameNameMode": "drop"}}] if more else []
    return {
        "type": "stat",
        "title": title,
        "targets": queries,
        "transformations": [*merge, organize(names, hide)],
        "fieldConfig": {
            "defaults": {"color": {"mode": "fixed", "fixedColor": BOX}}
            | ({"unit": unit} if unit else {})
            | ({} if decimals is None else {"decimals": decimals}),
            "overrides": list(overrides),
        },
        "options": {
            "reduceOptions": {"fields": "/.*/"},
            "colorMode": "background_solid",
            "graphMode": "none",
            "textMode": "value_and_name",
            # auto: a grid, two boxes per line in a row's first panel
            "orientation": orientation,
            "minVizWidth": 100,
            "minVizHeight": 60,
            "justifyMode": "auto",  # left
            "wideLayout": False,
            "text": TEXT,
        },
    }


def tile(title, url, key, kind="number", scale=None, root="data", unit=None, decimals=None):
    """One value of the twin's state, its name inside the tile, since a title would be cut short; with a
    `scale` ("/1000"), the API's column in other units."""
    columns, computed, hide = [(key, title, kind)], (), ()
    if scale:
        columns, computed, hide = [(key, key)], [(f"{key}{scale}", title)], [key]
    panel = stat("", url, columns, (), computed, root, hide, unit=unit, decimals=decimals)
    # the panel is the box
    panel["options"] |= {"orientation": "vertical", "colorMode": "none", "justifyMode": "center"}
    return panel


def table(title, url, columns, overrides=(), sort=None, header=True):
    """An API table; `sort`: by this column, latest first."""
    panel = {
        "type": "table",
        "title": title,
        "targets": [target(url, columns)],
        "transformations": [organize([c[1] for c in columns])],
        # every column in view; 1,024 as elsewhere
        "fieldConfig": {
            "defaults": {"unit": "locale", "custom": {"minWidth": 70}},
            "overrides": list(overrides),
        },
    }
    if sort:
        panel["transformations"].append(
            {"id": "sortBy", "options": {"sort": [{"field": sort, "desc": True}]}}
        )
    if not header:
        panel["options"] = {"showHeader": False}
    return panel

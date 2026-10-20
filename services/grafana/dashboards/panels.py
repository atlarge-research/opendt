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
COLORS = {"red": RED, "orange": ORANGE, "yellow": YELLOW, "green": GREEN, "blue": BLUE}
MARKERS = "rgba(255, 255, 255, 0.35)"  # light, so the data stays in front
BOX = "rgba(128, 128, 128, 0.15)"  # a box in a panel, on the dark and the light theme
# Grafana's dark theme: text, text of less weight, lines, and the text of most weight
# the theme's text, fainter, and lines, on the dark and the light theme
INK, FAINT, LINE = "inherit", "rgba(128, 128, 128, 0.9)", "rgba(128, 128, 128, 0.4)"
WHITE = "#ffffff"
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
    """A time series of an API table; `colors` maps each shown field to its colour, in legend order."""

    # the legend gives each line its axis' unit, except a percentage, which shows its own %
    def named(name):
        found = re.search(r"\[.+\]$", right[1] if right and name == right[0] else axis)
        return f"{name} {found.group()}" if found and unit != "percentunit" else name

    names = {name: named(name) for name in colors}
    columns = [(c[0], names.get(c[1], c[1]), *c[2:]) for c in columns]
    computed = [(e, names.get(n, n)) for e, n in computed]
    custom = {"axisLabel": axis, "lineWidth": 2, "showPoints": "never", **custom}
    if signed:  # below 0 too, and the axis still shows 0
        custom |= {"axisSoftMin": 0, "axisSoftMax": 0}
    defaults = ({} if signed else {"min": 0}) | {"decimals": decimals, "custom": custom}
    defaults |= {"unit": unit} if unit else {}
    overrides = {names[n]: {"color": {"mode": "fixed", "fixedColor": c}} for n, c in colors.items()}
    for name in apart:  # dashed (bars: lighter), to tell them apart in grayscale
        bars = custom.get("drawStyle") == "bars"
        overrides[names[name]] |= (
            {"custom__fillOpacity": 35} if bars else {"custom__lineStyle": DASHED}
        )
    if right:  # (field, label) of a second axis
        overrides[names[right[0]]] |= {
            "custom__axisPlacement": "right",
            "custom__axisLabel": right[1],
        }
    if better:  # "higher" or "lower"
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
            # the latest value; with gaps, the latest there is
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
            "justifyMode": "auto",
            "wideLayout": False,
            "text": TEXT,
        },
    }


def tiles(url, columns, computed=(), hide=(), root="data", unit=None, decimals=None):
    """Values of the twin's state side by side in one tile, each with its name, since a title would be cut short."""
    panel = stat("", url, columns, (), computed, root, hide, unit=unit, decimals=decimals)
    # the panel is the box
    panel["options"] |= {"orientation": "vertical", "colorMode": "none", "justifyMode": "center"}
    return panel


def tile(
    title,
    url,
    key,
    kind="number",
    scale=None,
    root="data",
    unit=None,
    decimals=None,
    limit=None,
    color=None,
):
    """One value of the twin's state; with a `scale` ("/1000"), the API's column in other units; with a `color`,
    the value in it, as its line in the plots; with a `limit`, green under it and red from it on."""
    columns, computed, hide = [(key, title, kind)], (), ()
    if scale:
        columns, computed, hide = [(key, key)], [(f"{key}{scale}", title)], [key]
    panel = tiles(url, columns, computed, hide, root, unit, decimals)
    if color:
        panel["fieldConfig"]["defaults"]["color"]["fixedColor"] = color
        panel["options"]["colorMode"] = "value"
    if limit is not None:
        steps = [{"value": None, "color": GREEN}, {"value": limit, "color": RED}]
        panel["fieldConfig"]["defaults"] |= {
            "color": {"mode": "thresholds"},
            "thresholds": {"mode": "absolute", "steps": steps},
        }
        panel["options"]["colorMode"] = "value"
    return panel


def table(title, url, columns, overrides=(), sort=None, header=True):
    """An API table; `sort`: by this column, latest first."""
    panel = {
        "type": "table",
        "title": title,
        "targets": [target(url, columns)],
        "transformations": [organize([c[1] for c in columns])],
        # thousands separators, as elsewhere; minWidth: every column in view
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


def editable(title, url, columns, save, delete, key="id"):
    """A table edited in place (Business Table): Edit and Delete on each row, Add in the header. A saved row goes
    to `save` with its cells in the address, an added one too but without `key` (it names a row, sent but not
    shown), a deleted one to `delete` (`${payload.<column>}` names a cell). Columns are (field, name, editor),
    the editor "number", "string", "-" (shown, not edited), or the URL of a list whose names a select offers."""

    def editor(field, kind):
        if kind in ("number", "string", "-"):
            return {"type": "number" if kind == "number" else "string"}
        return {
            "type": "select",
            "queryOptions": {"source": field, "value": "name", "label": "name"},
        }

    def item(field, name, kind, shown=True):
        edit = {"enabled": shown and kind != "-", "editor": editor(field, kind)}
        return {
            "enabled": shown,
            "field": {"name": field, "source": "A"},
            "label": name,
            "type": "auto",
            "aggregation": "none",
            "group": False,
            "edit": {**edit, "permission": {"mode": "", "userRole": []}},
            "newRowEdit": edit,
            # wide enough for a cell's editor, and for the longest names (2x Xeon Gold 6248R)
            "appearance": {
                "width": {"auto": True, "min": 60 if kind == "number" else 150},
                "wrap": False,
            },
        }

    def request(address):
        query = {**target(address, []), "refId": "save", "url_options": {"method": "POST"}}
        return {"datasource": DS["uid"], "payload": query}

    def cells(fields):
        query = "&".join(f"{f}=${{payload.{f}:percentencode}}" for f in fields)
        return f"{save}{'&' if '?' in save else '?'}{query}"

    fields = [c[0] for c in columns]
    allowed = {"enabled": True, "permission": {"mode": "", "userRole": []}}
    table = {
        "name": title,
        "items": [item(key, "", "number", shown=False), *(item(*c) for c in columns)],
        "update": request(cells([key, *fields])),
        "addRow": {**allowed, "request": request(cells(fields))},
        "deleteRow": {**allowed, "request": request(delete)},
    }
    kinds = [(f, f, "number" if e == "number" else "string") for f, _, e in columns]
    lists = [(f, e) for f, _, e in columns if e not in ("number", "string", "-")]
    return {
        "type": "volkovlabs-table-panel",
        "title": title,
        "targets": [
            target(url, [(key, key, "string"), *kinds]),  # a number or a name
            *({**target(u, [("name", "name", "string")]), "refId": f} for f, u in lists),
        ],
        "fieldConfig": {"defaults": {"unit": "locale"}, "overrides": []},
        "options": {"tables": [table]},
    }


def ratio(title, url, part, whole, colors):
    """A share as a percentage with the counts over it (e.g., 90/277); `part` and `whole` are the API's columns,
    or sums of them; its colour from each share of `colors` on ({share: name})."""
    names = sorted(set(re.findall(r"[a-z_]+", f"{part} {whole}")))
    shares = [(f"({part}) / ({whole})", "share"), (f'{part} + "/" + ({whole})', "counts", "string")]
    panel = stat(title, url, [(n, n) for n in names], computed=shares, hide=names)
    mappings = [  # the counts name the share
        {"fieldName": "counts", "handlerKey": "field.name"},
        {"fieldName": "share", "handlerKey": "field.value"},
    ]
    panel["transformations"].append({"id": "rowsToFields", "options": {"mappings": mappings}})
    steps = [{"value": share or None, "color": COLORS[c]} for share, c in sorted(colors.items())]
    panel["fieldConfig"]["defaults"] |= {
        "unit": "percentunit",
        "decimals": 0,
        "color": {"mode": "thresholds"},
        "thresholds": {"mode": "absolute", "steps": steps},
    }
    panel["options"]["colorMode"] = "value"
    return panel

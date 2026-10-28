"""Grafana's v2 dashboard format: elements, layouts, variables, and the decisions markers."""

from panels import API, DS, MARKERS, WEEK, status, target


def data_query(target):
    spec = {k: v for k, v in target.items() if k != "refId"}
    return {
        "kind": "DataQuery",
        "group": DS["type"],
        "version": "v0",
        "datasource": {"name": DS["uid"]},
        "spec": spec,
    }


def element(i, panel):
    """A panel as a v2 element, as Grafana converts a classic one."""
    queries = [
        {
            "kind": "PanelQuery",
            "spec": {"refId": t["refId"], "hidden": False, "query": data_query(t)},
        }
        for t in panel.get("targets", [])
    ]
    transformations = [{"kind": t["id"], "spec": t} for t in panel.get("transformations", [])]
    return {
        "kind": "Panel",
        "spec": {
            "id": i,
            "title": panel["title"],
            "description": panel.get("description", ""),
            "transparent": panel.get("transparent", False),
            "links": [],
            "data": {
                "kind": "QueryGroup",
                "spec": {
                    "queries": queries,
                    "transformations": transformations,
                    "queryOptions": {},
                },
            },
            "vizConfig": {
                "kind": "VizConfig",
                "group": panel["type"],
                "version": "",
                "spec": {
                    "options": panel.get("options", {}),
                    "fieldConfig": panel.get("fieldConfig", {"defaults": {}, "overrides": []}),
                },
            },
        },
    }


def grid(placed):
    """A fixed grid: (name, x, y, width, height) per panel."""
    items = [
        {
            "kind": "GridLayoutItem",
            "spec": {
                "x": x,
                "y": y,
                "width": w,
                "height": h,
                "element": {"kind": "ElementReference", "name": name},
            },
        }
        for name, x, y, w, h in placed
    ]
    return {"kind": "GridLayout", "spec": {"items": items}}


def when(variable, operator, *values):
    """Shown while `variable` matches (operator "equals" or "notEquals") any of the values."""
    rules = [
        {
            "kind": "ConditionalRenderingVariable",
            "spec": {"variable": variable, "operator": operator, "value": v},
        }
        for v in values
    ]
    return {
        "kind": "ConditionalRenderingGroup",
        "spec": {"visibility": "show", "condition": "or", "items": rules},
    }


def picked(*names):
    """Shown while any of these plots is not hidden."""
    return when("hidden", "notEquals", *names)


def all_of(*rules):
    """Shown while every rule holds, each of one condition."""
    items = [item for rule in rules for item in rule["spec"]["items"]]
    return {
        "kind": "ConditionalRenderingGroup",
        "spec": {"visibility": "show", "condition": "and", "items": items},
    }


def auto(shown, columns):
    """An auto grid of equal panels, each with the rule that shows it: (name, rule)."""
    items = [
        {
            "kind": "AutoGridLayoutItem",
            "spec": {
                "element": {"kind": "ElementReference", "name": name},
                "conditionalRendering": rule,
            },
        }
        for name, rule in shown
    ]
    spec = {
        "maxColumnCount": columns,
        "columnWidthMode": "narrow",
        "rowHeightMode": "standard",
        "fillScreen": False,
    }
    return {"kind": "AutoGridLayout", "spec": {**spec, "items": items}}


def row(title, layout, shown):
    spec = {"title": title, "collapse": False, "layout": layout}
    if not title:
        spec["hideHeader"] = True
    return {"kind": "RowsLayoutRow", "spec": spec | {"conditionalRendering": shown}}


def query(name, target):
    """A hidden variable of a query's first column, asked again at every refresh of the screen."""
    return {
        "kind": "QueryVariable",
        "spec": {
            "name": name,
            "current": {"text": "", "value": ""},
            # Infinity's own form for a variable's query
            "query": data_query({"queryType": "infinity", "infinityQuery": target}),
            "refresh": "onTimeRangeChanged",
            "regex": "",
            "sort": "disabled",
            "options": [],
            "multi": False,
            "includeAll": False,
            "allowCustomValue": False,
            "hide": "hideVariable",
            "skipUrlSync": True,
        },
    }


def custom(name, label, values, multi=False, current=None):
    """A variable the control panel sets; hidden from Grafana's own bar."""
    current = current or (values if multi else values[0])
    return {
        "kind": "CustomVariable",
        "spec": {
            "name": name,
            "label": label,
            "query": ",".join(values),
            "current": {"text": current, "value": current},
            "options": [
                {"text": v, "value": v, "selected": v in current if multi else v == current}
                for v in values
            ],
            "multi": multi,
            "includeAll": False,
            "allowCustomValue": False,
            "hide": "hideVariable",
            "skipUrlSync": False,
        },
    }


# a marker's text, on hover: what changed, and by whom (e.g., Hosts 277 to 2,770 (Manual))
EVENTS = target(
    f"{API}/api/events?markers=$markers",
    [("time", "time", "timestamp"), ("text", "change", "string"), ("by", "by", "string")],
    [("change + ' (' + by + ')'", "text", "string")],
)
ANNOTATION = {
    "kind": "AnnotationQuery",
    "spec": {
        "name": "Decisions",
        "enable": True,
        "hide": True,  # switched in the control panel
        "iconColor": MARKERS,
        "query": data_query(EVENTS),
    },
}


def dashboard(uid, title, panels, layout, variables=(), window="day"):
    """A screen; `window`, its time at the start (week, day, or hours, the last 6)."""
    return {
        "apiVersion": "dashboard.grafana.app/v2beta1",
        "kind": "Dashboard",
        "metadata": {"name": uid},
        "spec": {
            "title": title,
            "description": "",
            "tags": ["opendt"],
            "cursorSync": "Crosshair",  # one crosshair over all graphs
            "editable": True,
            "liveNow": False,
            "preload": False,
            "links": [],
            "annotations": [ANNOTATION],
            "elements": {
                name: element(i, panel) for i, (name, panel) in enumerate(panels.items(), 1)
            },
            "layout": {"kind": "RowsLayout", "spec": {"rows": layout}},
            "variables": [
                custom("markers", "Decisions", ["on", "off"]),
                custom("window", "Time", ["week", "day", "hours"], current=window),
                # the CO₂ zone the twin runs on now, named with every carbon intensity
                query("zone", status("carbon_zone")),
                *variables,
            ],
            "timeSettings": {
                "timezone": "utc",
                **WEEK,
                "autoRefresh": "5s",
                "autoRefreshIntervals": ["5s", "10s", "30s", "1m", "5m"],
                "hideTimepicker": True,  # the control panel's Time instead; so full screen has no top bar
                "fiscalYearStartMonth": 0,
            },
        },
    }

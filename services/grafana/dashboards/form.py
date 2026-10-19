"""The control panel of every screen and the plot picker: Business Forms panels, their code in js/."""

import json
from pathlib import Path

from panels import BROWSER_API, PERIODS, WEEK

JS = Path(__file__).parent / "js"
STATUS = f"{BROWSER_API}/api/status"
SCREENS = [
    ("opendt-overview", "Detailed"),
    ("opendt-simple", "Simple"),
    ("opendt-topology", "Topology"),
    ("opendt-tutorial", "Tutorial"),
]
VIEW = ["screen", "window", "period", "markers", "infrastructure"]  # never sent to the twin
ZONES = ["NL", "PL", "DE", "RO"]  # the API's twin.CARBON_TRACES; SURF's twin starts on NL
SCHEDULERS = ["Mem", "CoreMem", "ActiveServers", "ActiveServersInv", "ProvisionedCores", "Random"]
SPEEDS = [(1, "1x (real time)"), (60, "60x"), (300, "300x"), (3600, "3,600x"), (-1, "Maximum")]


def script(*names, **consts):
    """The code in js/<names>, after the constants it uses."""
    head = "".join(f"const {k} = {json.dumps(v)};\n" for k, v in consts.items())
    return head + "".join((JS / name).read_text() for name in names)


def option(value, label):
    return {"id": str(value), "label": label, "value": value}


def field(key, title, kind, **more):
    return {"uid": key, "id": key, "title": title, "type": kind, "labelWidth": 14, **more}


def select(key, title, choices, kind="select", **more):
    return field(key, title, kind, options=[option(v, label) for v, label in choices], **more)


# the widgets: buttons for a few short choices, a list for many or long ones, a slider for a small range,
# a number for an exact one
ZONE = select(
    "carbon_zone",
    "CO₂ zone",
    [(z, z) for z in ZONES],
    "radio",
    tooltip="Electricity Maps zones: Netherlands, Poland, Germany, Romania",
)
SCHEDULER = select(
    "scheduler",
    "Scheduler",
    [(s, s) for s in SCHEDULERS],
    tooltip="OpenDC's placement policy; Mem is OpenDC's default",
)
SPEED = select("speed_factor", "Speed", SPEEDS)
CALIBRATION = select("calibration", "Calibration", [(True, "On"), (False, "Off")], "radio")
# the calibrator's; each OpenDC run takes about 1.3 GB, so 4 or more parallel runs need more memory for Docker
CALIBRATOR = [
    select("parallel_simulations", "Parallel runs", [(n, str(n)) for n in (1, 2, 4, 8)], "radio"),
    field("calibration_min", "r from", "slider", min=0.5, max=20, step=0.5),
    field("calibration_max", "r to", "slider", min=0.5, max=20, step=0.5),
    field("calibration_points", "Values of r", "slider", min=2, max=20, step=1),
    select("mape_window", "MAPE window", [(60, "1 h"), (360, "6 h"), (1440, "24 h")], "radio"),
]
# the first group of hosts: SURF's, until changed on Topology
HOSTS = field("hosts", "Hosts", "number", min=1)
# the Topology screen, where the hosts are edited group by group
INFRASTRUCTURE = {
    "uid": "infrastructure",
    "id": "infrastructure",
    "title": "",
    "type": "link",
    "value": "/d/opendt-topology",
    "linkText": "✎ Infrastructure",
    "target": "_self",
}
CONFIRM = {
    "title": "Apply",
    "body": "The view changes at once, the twin from its next window of operation.",
    "columns": {"name": "", "oldValue": "Now", "newValue": "New"},
    "confirm": "Apply",
}


def form(elements, initial_code, update_code, **options):
    """A Business Forms panel on the API: its values from /api/status, its changes, once applied and
    confirmed, to /api/control (from the browser, to the API's port)."""
    return {
        "type": "volkovlabs-form-panel",
        "options": {
            "initial": {"method": "GET", "url": f"{BROWSER_API}/api/status", "code": initial_code},
            "update": {
                "method": "PATCH",
                "url": f"{BROWSER_API}/api/control",
                "payloadMode": "custom",
                "getPayload": script("changed.js", "payload.js", view=VIEW),
                "confirm": True,
                "code": update_code,
            },
            "sync": False,  # true would reload the values at every refresh, over what is being typed
            "elements": elements,
            "confirmModal": CONFIRM,
            **options,
        },
    }


def fit(element, width):
    """An element in a tile: no tooltip (no room for its icon), a link without a label, a slider as wide as
    it takes."""
    fitted = {k: v for k, v in element.items() if k != "tooltip"}
    if element["type"] == "link":
        return fitted | {"labelWidth": 1, "width": 20}
    if element["type"] == "slider":
        return fitted | {"labelWidth": width}
    return fitted | {"labelWidth": width, "width": 11}


def lever(elements, split=False):
    """Levers in a tile of the top bar: their values now and, once changed, Apply with a pencil; `split`:
    in two columns."""
    width = 13 if split else 9  # of the labels
    tile = [fit(e, width) for e in elements]
    layout = {}
    if split:
        half = (len(tile) + 1) // 2
        tile = [{**e, "section": "left" if i < half else "right"} for i, e in enumerate(tile)]
        sections = [{"id": side, "name": ""} for side in ("left", "right")]
        layout = {"layout": {"variant": "split", "sections": sections}}
    panel = form(
        tile,
        "",
        script("changed.js", "range.js", "applied.js", week=WEEK),
        submit={"text": "Apply", "icon": "pen"},
        reset={"variant": "hidden"},
        buttonGroup={"orientation": "left", "size": "sm"},
        **layout,
    )
    return {**panel, "title": ""}


def control(screen, own_fields=(), period=True):
    """The control panel: what the screen shows, then the screen's own fields, so the same rows sit in the
    same places on every screen. Nothing changes before Apply: then the changed levers go to the twin and the
    view follows."""
    view = [
        select("screen", "Screen", SCREENS, value=screen),
        select(
            "window",
            "Time",
            [("week", "Week"), ("day", "Day"), ("hours", "6 h")],
            "radio",
            value="week",
        ),
        # the markers on the graphs
        select("markers", "Decisions", [("on", "On"), ("off", "Off")], "radio", value="on"),
    ]
    # the time, the interval, and the markers come from the address
    start = {"screen": screen}
    if period:
        own_fields = [
            select("period", "Interval", [(p, p) for p in PERIODS], value="day"),
            *own_fields,
        ]
    panel = form(
        [*view, *own_fields],
        script("range.js", "initial.js", "follow.js", start=start, week=WEEK, status=STATUS),
        script("changed.js", "range.js", "applied.js", week=WEEK),
        submit={"text": "Apply"},
        reset={"text": "Full screen", "icon": "monitor", "variant": "secondary"},
        resetAction={"mode": "custom", "code": script("full_screen.js"), "confirm": False},
    )
    return {**panel, "title": "OpenDT"}


def picker(title, plots):
    """The plots of a row, ticked while shown; a change shows or hides a plot at once."""
    mine = list(plots)
    boxes = [option(key, plot["title"].replace("$period", "period")) for key, plot in plots.items()]
    return {
        "type": "volkovlabs-form-panel",
        "title": title,
        "options": {
            "initial": {"method": "-", "code": script("shown.js", mine=mine)},
            "update": {"method": "-"},
            "updateEnabled": "disabled",  # no buttons
            "elementValueChanged": script("pick.js", mine=mine),
            "sync": False,
            "elements": [
                field("plots", "", "checkboxList", labelWidth=1, options=boxes, value=mine)
            ],
        },
    }

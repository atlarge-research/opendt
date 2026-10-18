"""The control panel of every screen and the plot picker: Business Forms panels, their code in js/."""

import json
from pathlib import Path

from panels import BROWSER_API, PERIODS, WEEK

JS = Path(__file__).parent / "js"
SCREENS = [
    ("opendt-overview", "Detailed"),
    ("opendt-simple", "Simple"),
    ("opendt-topology", "Topology"),
    ("opendt-tutorial", "Tutorial"),
]
VIEW = ["screen", "window", "period", "markers"]  # what the screen shows, never sent to the twin
ZONES = ["NL", "PL", "DE", "RO"]  # the API's twin.CARBON_TRACES; SURF's twin starts on NL
SCHEDULERS = ["Mem", "CoreMem", "ActiveServers", "ActiveServersInv", "ProvisionedCores", "Random"]
SPEEDS = [(1, "1x (real time)"), (60, "60x"), (300, "300x"), (3600, "3,600x"), (-1, "Maximum")]
# the API's twin.SERVERS: SURF's node and OpenDC web's host templates
KINDS = [
    ("H01", "SURF-SARA (16 cores)"),
    ("EPYC", "EPYC (64 cores)"),
    ("Xeon", "Xeon (40 cores)"),
    ("Memory", "Memory (48 cores, 1,024 GB)"),
    ("Edge", "Edge (8 cores)"),
]


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


TWIN_LEVERS = [
    select(
        "carbon_zone",
        "CO₂ zone",
        [(z, z) for z in ZONES],
        tooltip="Electricity Maps zones: Netherlands, Poland, Germany, Romania",
    ),
    select(
        "scheduler",
        "Scheduler",
        [(s, s) for s in SCHEDULERS],
        tooltip="OpenDC's placement policy; Mem is OpenDC's default",
    ),
    select("speed_factor", "Speed factor", SPEEDS),
]
# the calibrator's; each OpenDC run takes about 1.3 GB, so 4 or more parallel runs need more memory for Docker
CALIBRATION_LEVERS = [
    select("calibration", "Calibration", [(True, "On"), (False, "Off")], "radio"),
    select("parallel_simulations", "Parallel runs", [(n, str(n)) for n in (1, 2, 4, 8)]),
    field("calibration_min", "r from", "number", min=0),
    field("calibration_max", "r to", "number", min=0),
    field("calibration_points", "Values of r", "number", min=2),
    select("mape_window", "MAPE window", [(60, "1 h"), (360, "6 h"), (1440, "24 h")]),
]
# the first group of hosts: SURF's, until changed on Topology
HOSTS = field("count_1", "Hosts", "number", min=1)


def control(screen, own_fields, period=True):
    """The control panel: what the screen shows, the twin's levers, then the screen's own fields, so the
    same rows sit in the same places on every screen. Nothing changes before Apply: then the changed levers
    go to /api/control (from the browser, to the API's port) and the view follows."""
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
    # the interval and the markers come from the address
    start = {"screen": screen, "window": "week"}
    if period:
        own_fields = [
            select("period", "Interval", [(p, p) for p in PERIODS], value="day"),
            *own_fields,
        ]
    return {
        "type": "volkovlabs-form-panel",
        "title": "OpenDT",
        "options": {
            "initial": {
                "method": "GET",
                "url": f"{BROWSER_API}/api/status",
                "code": script("initial.js", start=start),
            },
            "update": {
                "method": "PATCH",
                "url": f"{BROWSER_API}/api/control",
                "payloadMode": "custom",
                "getPayload": script("changed.js", "payload.js", view=VIEW),
                "confirm": True,
                "code": script("changed.js", "applied.js", week=WEEK),
            },
            "sync": False,  # true would reload the values at every refresh, over what is being typed
            "elements": view + TWIN_LEVERS + CALIBRATION_LEVERS + own_fields,
            "submit": {"text": "Apply"},
            "reset": {"text": "Full screen", "icon": "monitor", "variant": "secondary"},
            "resetAction": {"mode": "custom", "code": script("full_screen.js"), "confirm": False},
            "confirmModal": {
                "title": "Apply",
                "body": "The view changes at once, the twin from its next window of operation.",
                "columns": {"name": "", "oldValue": "Now", "newValue": "New"},
                "confirm": "Apply",
            },
        },
    }


def group(i):
    """Group i of hosts, a kind and a count; group 3 shows once group 2 has a kind."""
    shown = (
        {"showIf": "return context.panel.elements.find((e) => e.id === 'kind_2').value"}
        if i == 3
        else {}
    )
    return [
        select(f"kind_{i}", f"Hosts {i}", KINDS, **shown),
        field(f"count_{i}", f"Count {i}", "number", min=0, **shown),
    ]


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

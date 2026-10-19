"""The control panel of every screen and the plot picker: Business Forms panels, their code in js/."""

import json
from pathlib import Path

from panels import BROWSER_API, PERIODS, STATUS, WEEK, target

JS = Path(__file__).parent / "js"
BROWSER_STATUS = f"{BROWSER_API}/api/status"
SCREENS = [
    ("opendt-overview", "Detailed"),
    ("opendt-simple", "Simple"),
    ("opendt-topology", "Topology"),
    ("opendt-tutorial", "Tutorial"),
]
VIEW = ["window", "period", "markers"]  # what the screen shows, never sent to the twin
ZONES = ["NL", "PL", "DE", "RO"]  # the API's twin.CARBON_TRACES; SURF's twin starts on NL
SCHEDULERS = ["Mem", "CoreMem", "ActiveServers", "ActiveServersInv", "ProvisionedCores", "Random"]
SPEEDS = [(1, "Real time"), (60, "60x"), (300, "300x"), (3600, "3,600x"), (-1, "Maximum")]


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
PARALLEL = select(
    "parallel_simulations", "Parallel runs", [(n, str(n)) for n in (1, 2, 4, 8)], "radio"
)
R_FROM = field("calibration_min", "r from", "slider", min=0.5, max=20, step=0.5)
R_TO = field("calibration_max", "r to", "slider", min=0.5, max=20, step=0.5)
R_VALUES = field("calibration_points", "Values of r", "slider", min=2, max=20, step=1)
MAPE_WINDOW = select(
    "mape_window", "MAPE window", [(60, "1 h"), (360, "6 h"), (1440, "24 h")], "radio"
)
# the first group of hosts: SURF's, until changed on Topology
HOSTS = field("hosts", "Hosts", "number", min=1)
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
            "initial": {"method": "GET", "url": BROWSER_STATUS, "code": initial_code},
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


def control(own_fields=(), period=True):
    """The control panel: what the screen shows, then the screen's own fields, so the same rows sit in the
    same places on every screen. Nothing changes before Apply: then the changed levers go to the twin and the
    view follows."""
    view = [
        select(
            "window",
            "Period",
            [("week", "Week"), ("day", "Day"), ("hours", "6 h")],
            "radio",
            value="week",
        ),
        # the markers on the graphs
        select("markers", "Decisions", [("on", "On"), ("off", "Off")], "radio", value="on"),
    ]
    if period:
        own_fields = [
            select("period", "Interval", [(p, p) for p in PERIODS], value="day"),
            *own_fields,
        ]
    panel = form(
        [*view, *own_fields],
        script("range.js", "initial.js", "follow.js", "retry.js", week=WEEK, status=STATUS),
        script("changed.js", "range.js", "applied.js", week=WEEK),
        submit={"text": "Apply"},
        reset={"text": "Full screen", "icon": "monitor", "variant": "secondary"},
        resetAction={"mode": "custom", "code": script("full_screen.js"), "confirm": False},
    )
    return {**panel, "title": ""}  # under the logo and the name


BOX = """.lever { min-height: 80px; height: 100%; display: flex; flex-direction: column; align-items: center;
  justify-content: center; gap: 4px; cursor: pointer; container-type: inline-size; }
.lever small { font-size: 12px; white-space: nowrap; }
.lever b { font-size: min(24px, 18cqw); font-weight: 500; white-space: nowrap; }
.lever i { font-style: normal; }
.lever a { font-size: 11px; color: #8e8e8e; white-space: nowrap; }
.lever:hover a { color: #6e9fff; }"""
# a box, once clicked: larger, over the screen, with what its levers take
OPEN = """.opendt-lever { position: absolute; z-index: 1000; display: flex; flex-direction: column; gap: 6px;
  padding: 12px; background: #181b1f; border: 1px solid #3d71d9; border-radius: 2px; color: #ccccdc;
  font-size: 14px; text-align: center; }
.opendt-lever small { font-size: 12px; }
.opendt-lever button, .opendt-lever input { padding: 6px; background: #111217; color: #ccccdc;
  border: 1px solid #2f3238; border-radius: 2px; font-size: 14px; text-align: center; cursor: pointer; }
.opendt-lever .on, .opendt-lever .apply { background: #3d71d9; border-color: #3d71d9; color: white; }
.opendt-lever div { display: flex; gap: 6px; margin-top: 6px; }
.opendt-lever div button { flex: 1; }"""


def value(element):
    """A lever's value in a box, and what it takes: one of its choices, or a number."""
    key = element["id"]
    data = {"key": key, "value": f"{{{{{key}}}}}"}
    if "options" in element:
        values = [o["value"] for o in element["options"]]
        data["choices"] = ",".join(v if isinstance(v, str) else json.dumps(v) for v in values)
        data["labels"] = "|".join(o["label"] for o in element["options"])  # 3,600x
    else:
        data |= {k: element[k] for k in ("min", "max", "step") if k in element}
    return "<i" + "".join(f' data-{k}="{v}"' for k, v in data.items()) + f">{{{{{key}}}}}</i>"


def box(*elements, title=None, link=None):
    """Levers in a box, as values of the twin's: their values now (two: from-to); a click opens the box larger,
    with what they take, and Apply, once confirmed, sends them to the twin (from the browser, to the API's port);
    `link`: (text, address)."""
    title = title or elements[0]["title"]
    more = f'<a href="{link[1]}">{link[0]}</a>' if link else ""
    content = (
        f'<div class="lever" data-name="{title}"><small>{title} <a>✎</a></small>'
        f"<b>{'-'.join(map(value, elements))}</b>{more}</div>"
    )
    return {
        "type": "marcusolsson-dynamictext-panel",
        "title": "",
        "targets": [
            target(STATUS, [(e["id"], e["id"], "string") for e in elements]) | {"root_selector": ""}
        ],
        "options": {
            "renderMode": "everyRow",
            "content": content,
            "defaultContent": f'<div class="lever"><small>{title}</small><b>…</b></div>',
            "styles": BOX,
            "afterRender": script("box.js", control=f"{BROWSER_API}/api/control", style=OPEN),
        },
    }


TAB = "padding: 2px 8px; border-radius: 2px; color: #ccccdc"


# the window of the plots shown, over the screen
DIALOG = """.opendt-plots { position: fixed; inset: 0; z-index: 1000; display: flex; align-items: center;
  justify-content: center; background: rgba(0, 0, 0, 0.6); }
.opendt-plots > div { background: #181b1f; border: 1px solid #2f3238; border-radius: 4px; padding: 24px;
  color: #ccccdc; font-size: 14px; }
.opendt-plots section { display: grid; grid-template-columns: repeat(4, auto); gap: 40px; margin: 16px 0 24px; }
.opendt-plots label { display: flex; gap: 8px; margin-top: 10px; cursor: pointer; }
.opendt-plots button { float: right; background: #3d71d9; color: white; border: 0; border-radius: 2px;
  padding: 6px 16px; cursor: pointer; }"""


def brand(uid, plots=()):
    """The logo and the name, and the screens: a click on one shows it, with the same time and markers;
    `plots`: (row, [(key, title)]) to show or hide, in a window that ☰ Plots opens."""
    tabs = "".join(
        f'<a data-href="/d/{key}?${{__url_time_range}}&${{markers:queryparam}}&kiosk" style="{TAB}'
        + ('; background: #3d71d9; color: white">' if key == uid else '">')
        + f"{name}</a>"
        for key, name in SCREENS
    )
    if plots:
        tabs += f'<a class="plots" style="{TAB}; margin-left: auto; cursor: pointer">☰ Plots</a>'
    html = (
        '<div style="display: flex; align-items: center; gap: 12px; font-size: 22px; font-weight: 600">'
        '<img src="/public/img/opendt.png" height="40">OpenDT</div>'
        f'<div style="display: flex; gap: 4px; margin-top: 10px; font-size: 14px">{tabs}</div>'
    )
    return {
        "type": "marcusolsson-dynamictext-panel",
        "title": "",
        "options": {
            "renderMode": "allRows",  # once, with or without data
            "content": html,
            "defaultContent": html,
            "afterRender": script("links.js", "footer.js")
            + (script("plots.js", plots=plots, style=DIALOG) if plots else ""),
        },
    }

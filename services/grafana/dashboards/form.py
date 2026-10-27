"""The top of every screen: the view (the logo, the screens, and what they show), then the twin's levers by
category; Business Text panels, their code in js/."""

import json
from pathlib import Path

from panels import BROWSER_API, PERIODS, WEEK, status, text

JS = Path(__file__).parent / "js"
SCREENS = [
    ("opendt-overview", "Dashboard"),
    ("opendt-topology", "Topology"),
    ("opendt-tutorial", "Tutorial"),
]
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
# the calibrator's; each OpenDC run takes up to about 1.3 GB, so 4 or 8 parallel runs need more memory for Docker
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


BOX = """.lever { height: 100%; display: flex; flex-direction: column; justify-content: center; gap: 2px;
  padding: 0 8px; cursor: pointer; }
.lever small { font-size: 12px; color: #8e8e8e; white-space: nowrap; }
.lever > small:first-child { margin-bottom: 2px; font-size: 14px; font-weight: 500; color: inherit; }
.lever p { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; margin: 0;
  line-height: 1.3; }
.lever b { font-size: 15px; font-weight: 500; white-space: nowrap; }
.lever > small:last-child { margin: 4px 0 0; font-size: 11px; }
.lever i { font-style: normal; }
.lever a { font-size: 11px; color: #8e8e8e; white-space: nowrap; }
.lever:hover a { color: #6e9fff; }"""
# a box, once clicked: larger, over the screen, with what its levers take; and a change sent, pulsing
OPEN = """.opendt-lever { position: absolute; z-index: 1000; display: flex; flex-direction: column; gap: 6px;
  padding: 12px; background: var(--panel); border: 1px solid #3d71d9; border-radius: 2px; color: var(--ink);
  font-size: 14px; }
.opendt-lever small { font-size: 12px; color: #8e8e8e; margin-top: 4px; }
.opendt-lever div { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.opendt-lever button, .opendt-lever input { flex: 1; padding: 6px; background: var(--canvas); color: var(--ink);
  border: 1px solid var(--line); border-radius: 2px; font-size: 14px; text-align: center; cursor: pointer; }
.opendt-lever input { width: 4em; }
.opendt-lever .on, .opendt-lever .apply { background: #3d71d9; border-color: #3d71d9; color: white; }
/* a change sent, until the twin follows it (box.js) */
.lever i.pending { padding: 0 4px; border-radius: 2px; background: #3d71d9; color: white;
  animation: opendt-pending 1.6s ease-in-out infinite; }
@keyframes opendt-pending { 50% { opacity: 0.55; } }"""


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


def group(title, levers, link=None, note=""):
    """Levers of a category in a box, as values of the twin's: each its name and its value now (two: from-to); a
    click opens the box larger, with what they take, and Apply, once confirmed, sends the changes to the twin (from
    the browser, to the API's port); `levers`: (name, elements); `link`: (text, address); `note`: under them."""
    lines = "".join(
        f'<p data-name="{name}"><small>{name}</small><b>{"-".join(map(value, elements))}</b></p>'
        for name, elements in levers
    )
    more = f'<a href="{link[1]}">{link[0]}</a>' if link else ""
    keys = [e["id"] for _, elements in levers for e in elements]
    return text(
        f'<div class="lever"><small>{title} <a>✎</a></small>{lines}{more}{note}</div>',
        script("css.js", "warn.js", "box.js", control=f"{BROWSER_API}/api/control", style=OPEN),
        [status(*keys)],
        f'<div class="lever"><small>{title}</small></div>',
        BOX,
    )


TAB = "padding: 2px 8px; border-radius: 2px; color: inherit; cursor: pointer; white-space: nowrap"
# the window of the plots shown, over the screen
DIALOG = """.opendt-plots { position: fixed; inset: 0; z-index: 1000; display: flex; align-items: center;
  justify-content: center; background: rgba(0, 0, 0, 0.6); }
.opendt-plots > div { background: var(--panel); border: 1px solid var(--line); border-radius: 4px; padding: 24px;
  color: var(--ink); font-size: 14px; }
.opendt-plots section { display: grid; grid-template-columns: repeat(4, auto); gap: 40px; margin: 16px 0 24px; }
.opendt-plots label { display: flex; gap: 8px; margin-top: 10px; cursor: pointer; }
.opendt-plots button { float: right; background: #3d71d9; color: white; border: 0; border-radius: 2px;
  padding: 6px 16px; cursor: pointer; }"""
VIEW = """.view { display: flex; flex-direction: column; gap: 8px; font-size: 14px; }
.view div { display: flex; align-items: center; gap: 4px; }
.view small { color: #8e8e8e; margin-left: 8px; margin-right: 2px; }
.view .on { background: #3d71d9; color: white !important; }
/* narrower on a laptop, so the row stays in its panel */
.view select { width: auto; min-width: 0; height: 26px; padding: 0 6px; background: transparent; color: inherit;
  border: 1px solid #8e8e8e; border-radius: 2px; }"""


def choose(key, choices):
    """A setting of the view as buttons; the one shown in blue."""
    return "".join(
        f'<a data-var="{key}" data-value="{v}" style="{TAB}">{label}</a>' for v, label in choices
    )


def brand(uid, plots=(), period=True):
    """The view: the logo, the twin's time, and the screens (a click on one shows it, with the same time and
    markers); then the time shown, the markers, the interval (`period`), and the theme, at once on a click; `plots`:
    (row, [(key, title)]) to show or hide, in a window that ☰ Plots opens."""
    tabs = "".join(
        f'<a data-href="/d/{key}?${{__url_time_range}}&${{markers:queryparam}}&kiosk" style="{TAB}'
        + ('; background: #3d71d9; color: white">' if key == uid else '">')
        + f"{name}</a>"
        for key, name in SCREENS
    )
    if plots:
        tabs += f'<a class="plots" style="{TAB}; margin-left: auto">☰ Plots</a>'
    view = choose("window", [("week", "Week"), ("day", "Day"), ("hours", "6 h")])
    view += "<small>Decisions</small>" + choose("markers", [("on", "On"), ("off", "Off")])
    if period:
        options = "".join(f"<option>{p}</option>" for p in PERIODS)
        view += f'<small>Interval</small><select data-var="period">{options}</select>'
    logo = (
        '<div style="gap: 12px; font-size: 22px; font-weight: 600"><img src="/public/img/opendt.png" height="36">'
        'OpenDT<span style="margin-left: auto; font-size: 14px; font-weight: 400" data-time="{{twin_time}}">'
        f'</span><a class="theme" style="{TAB}"></a></div>'  # light or dark, grafana.js
    )
    html = f'<div class="view">{logo}<div>{tabs}</div><div>{view}</div></div>'
    code = script(
        "links.js",
        "css.js",
        "grafana.js",
        "view.js",
        "plots.js",
        week=WEEK,
        plots=plots,
        style=DIALOG,
    )
    return text(html, code, [status("twin_time")], html.replace("{{twin_time}}", ""), VIEW)

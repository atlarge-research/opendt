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


def field(key, **more):
    return {"id": key, **more}


def select(key, choices, **more):
    return field(key, options=[{"label": label, "value": v} for v, label in choices], **more)


# the widgets (box.js): buttons for choices, a number otherwise
ZONE = select(
    "carbon_zone",
    [(z, z) for z in ZONES],
    tooltip="Electricity Maps zones: Netherlands, Poland, Germany, Romania",
)
SCHEDULER = select(
    "scheduler",
    [(s, s) for s in SCHEDULERS],
    tooltip="OpenDC's placement policy; Mem is OpenDC's default",
)
SPEED = select("speed_factor", SPEEDS)
CALIBRATION = select("calibration", [(True, "On"), (False, "Off")])
R_FROM = field("calibration_min", min=0.5, max=20, step=0.5)
R_TO = field("calibration_max", min=0.5, max=20, step=0.5)
R_VALUES = field("calibration_points", min=2, max=20, step=1)
MAPE_WINDOW = select("mape_window", [(60, "1 h"), (360, "6 h"), (1440, "24 h")])
# the first group of hosts: SURF's, until changed on Topology
HOSTS = field("hosts", min=1)


# the boxes in HTML, in the colours of Grafana's theme (Business Text fills in ${theme...}): in Grafana's own text
# (22 px lines), the Self-calibrator's lines and formula do not fit the bar
BOX = """.lever { height: 100%; display: flex; flex-direction: column; justify-content: center; gap: 2px;
  padding: 0 8px; cursor: pointer; }
.lever small { font-size: 12px; color: ${theme.colors.text.secondary}; white-space: nowrap; }
.lever > small:first-child { margin-bottom: 2px; font-size: 14px; font-weight: 500; color: inherit; }
.lever p { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; margin: 0;
  line-height: 1.3; }
.lever b { font-size: 15px; font-weight: 500; white-space: nowrap; }
.lever > small:last-child { margin: 4px 0 0; font-size: 11px; }
.lever i { font-style: normal; }
.lever a { font-size: 11px; color: ${theme.colors.text.secondary}; white-space: nowrap; }
.lever:hover a { color: ${theme.colors.text.link}; }
/* a change sent, until the twin follows it (box.js) */
.lever i.pending { padding: 0 4px; border-radius: 2px; background: ${theme.colors.primary.main};
  color: ${theme.colors.primary.contrastText};
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


def group(title, levers, link=None, note="", shown=()):
    """Levers of a category in a box, as values of the twin's: each its name and its value now (two: from-to); a
    click opens them in Grafana's dialog, with what they take, and Apply, once confirmed, sends the changes to the
    twin (from the browser, to the API's port); `levers`: (name, elements); `link`: (text, address); `note`: under
    them; `shown`: (name, key), the twin's values shown first, set in its config only."""
    lines = "".join(f"<p><small>{name}</small><b>{{{{{key}}}}}</b></p>" for name, key in shown)
    lines += "".join(
        f'<p data-name="{name}"><small>{name}</small><b>{"-".join(map(value, elements))}</b></p>'
        for name, elements in levers
    )
    more = f'<a href="{link[1]}">{link[0]}</a>' if link else ""
    keys = [key for _, key in shown] + [e["id"] for _, elements in levers for e in elements]
    return text(
        f'<div class="lever"><small>{title} <a>✎</a></small>{lines}{more}{note}</div>',
        script("ui.js", "warn.js", "box.js", control=f"{BROWSER_API}/api/control", title=title),
        [status(*keys)],
        f'<div class="lever"><small>{title}</small></div>',
        BOX,
    )


# the time shown (view.js): the window variable's values, and their buttons
WINDOWS = [("week", "Week"), ("day", "Day"), ("hours", "6 h")]


def brand(uid, plots=(), period=True):
    """The view, in Grafana's buttons (view.js): the logo, the twin's time, and the theme; the screens (a click on
    one shows it, with the same time and markers); then the time shown, the markers, and the interval (`period`), at
    once on a click; `plots`: (row, [(key, title)]) to show or hide, in Grafana's dialog that ☰ Plots opens."""
    code = script(
        "ui.js",
        "css.js",
        "grafana.js",
        "plots.js",
        "view.js",
        uid=uid,
        screens=SCREENS,
        windows=WINDOWS,
        decisions=[("on", "On"), ("off", "Off")],
        periods=PERIODS if period else [],
        plots=plots,
        week=WEEK,
    )
    # fixed, so Grafana's components in it stay over the refreshes (ui.js)
    return text('<div class="view"></div>', code, [status("twin_time")])

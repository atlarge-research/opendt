"""What each step of the Tutorial screen shows: tutorial/resources/tutorial.yaml, with the solutions of the
notebooks (questions.yaml)."""

from html import escape
from pathlib import Path

import yaml
from form import script
from panels import (
    BLUE,
    BROWSER_API,
    FAINT,
    GREEN,
    GREY,
    INK,
    LINE,
    RED,
    WHITE,
    YELLOW,
    text,
    timeseries,
)
from plots import ROWS, co2, hosts, power

RESOURCES = Path(__file__).resolve().parents[3] / "tutorial" / "resources"
STEPS = yaml.safe_load((RESOURCES / "tutorial.yaml").read_text())
QUESTIONS = yaml.safe_load((RESOURCES / "questions.yaml").read_text())
PLOTS = {"power": power, "co2": co2, "hosts": hosts}
PLOTS |= {key: plot for plots in ROWS.values() for key, plot in plots.items()}
# the trace's first day, as the notebooks simulate it (make_first_day.py): the same at any time of the twin
DAY = (RESOURCES / "first_day_power.csv").read_text()
CALIBRATION = (RESOURCES / "first_day_calibration.csv").read_text()
NO, SELF, LIMIT = (
    "No calibration (r = 4)",
    "Self-calibrating every hour",
    "Community-accepted threshold",
)
THRESHOLD = ("10", LIMIT)  # 10%, as notebook 1 draws it (question 1.1)
PLOTS |= {
    "first-day-power": timeseries(
        "Power draw, first day (notebook 1)",
        None,
        "Power draw [kW]",
        {"Ground truth": GREY, "OpenDT": GREEN},
        [("truth", "Ground truth"), ("opendt", "OpenDT")],
        apart=["Ground truth"],
        csv=DAY,
    ),
    "first-day-mape": timeseries(
        "Power draw MAPE per hour, first day (notebook 1)",
        None,
        "Power draw MAPE [%]",
        {"MAPE": RED, LIMIT: GREY},
        [("mape", "MAPE")],
        computed=[THRESHOLD],
        apart=[LIMIT],
        csv=DAY,
    ),
    "first-day-calibration": timeseries(
        "Power draw MAPE per hour, first day (notebook 2)",
        None,
        "Power draw MAPE [%]",
        {NO: RED, SELF: GREEN, LIMIT: GREY},
        [("r4", NO), ("calibrated", SELF)],
        computed=[THRESHOLD],
        apart=[NO, LIMIT],
        csv=CALIBRATION,
        lineInterpolation="stepAfter",
    ),
    "first-day-r": timeseries(
        "Calibration parameter r, first day (notebook 2)",
        None,
        "r",
        {"r": BLUE},
        [("r", "r")],
        csv=CALIBRATION,
        lineInterpolation="stepAfter",
    ),
}
# step n is ORDER[n - 1]: (use case, step)
ORDER = [(use_case, step) for use_case, items in STEPS.items() for step in items]
# the twin as step n starts, STARTS[n - 1]: as the live twin's configuration starts it, then as the steps before
# left it (their `set`), then as its own `start` says; opening a step sets it (step.js)
BASE = {"hosts": 277, "carbon_zone": "NL", "calibration": False}
BASE |= {"calibration_min": 3, "calibration_max": 9, "calibration_points": 7}  # r = 3, 4, ..., 9
STARTS, state = [], dict(BASE)
for _, step in ORDER:
    state |= step.get("start", {})
    STARTS.append(dict(state))
    state |= step.get("set", {})

# this screen as it is (time, full screen, ...), at another step; links.js and step.js fill in ${__url...}
HERE = "${__url.path}${__url.params:exclude:var-step}&var-step="
CIRCLE = (
    "display:inline-flex;align-items:center;justify-content:center;width:32px;height:32px;box-sizing:border-box;"
    "border-radius:50%;font-size:15px;font-weight:500;font-variant-numeric:tabular-nums;text-decoration:none"
)


def circled(n, current):
    """Step n in a circle, as the steps of a figure: filled if current, else a link to step n; ringed in the colour of
    how it was answered (step.js)."""
    if n == current:
        return f'<span data-step="{n}" style="{CIRCLE};background:{BLUE};color:{WHITE}">{n}</span>'
    return f'<a data-step="{n}" data-href="{HERE}{n}" style="{CIRCLE};border:1px solid {LINE};color:{INK}">{n}</a>'


def navigator(current):
    """The steps of each use case under its name."""
    groups = []
    for use_case in STEPS:
        numbers = [n for n, (case, _) in enumerate(ORDER, 1) if case == use_case]
        color = INK if current in numbers else FAINT
        circles = "".join(circled(n, current) for n in numbers)
        groups.append(
            f'<div><div style="font-size:14px;color:{color}">{escape(use_case)}</div>'
            f'<div style="display:flex;gap:8px;margin-top:4px">{circles}</div></div>'
        )
    return f'<div style="display:flex;flex-wrap:wrap;gap:12px 36px">{"".join(groups)}</div>'


def card(n):
    """Step n: the steps, its question, and its formula, as text; under them, drawn by step.js, what to change, its
    choices, and one of its parts at a time, then Hint and Solution, Back and Next."""
    _, step = ORDER[n - 1]
    solution = step.get("solution", QUESTIONS[step["question"]]["solution"])
    lines = [
        navigator(n),
        f'<p style="font-size:20px;margin:12px 0 0">'
        f"<strong>Question {n}:</strong> {escape(step['ask'])}</p>",
    ]
    if "formula" in step:  # OpenDC's power model, for the steps on r
        lines.append(f'<p style="font-size:18px;margin:6px 0 0">{step["formula"]}</p>')
    # the rest of the card's column, drawn by step.js
    lines.append('<div class="answer" style="display:flex;flex-grow:1;margin-top:8px"></div>')
    column = "display:flex;flex-direction:column;min-height:100%"
    content = f'<div style="{column}">' + "\n".join(lines) + "</div>"
    # late: yellow, darker on the light theme, as #F0E442 hardly shows on white
    colors = {"right": GREEN, "late": YELLOW, "late-light": "#998A00", "wrong": RED}
    code = script(
        "links.js",
        "ui.js",
        "warn.js",
        "step.js",
        change=f"{step['do']}." if "do" in step else None,
        choices=step["choices"],
        answer=step["answer"],
        hint=step["hint"],
        solution=solution.strip(),
        around=[
            (i, label) for i, label in [(n - 1, "Back"), (n + 1, "Next")] if 1 <= i <= len(ORDER)
        ],
        here=HERE,
        colors=colors,
        step=str(n),
        start=STARTS[n - 1],
        control=f"{BROWSER_API}/api/control",
        status=f"{BROWSER_API}/api/status",
    )
    return text(content, code)


# the values of the step variable, 1, 2, 3, ...: (value, step, card)
SLIDES = [(str(n), step, card(n)) for n, (_, step) in enumerate(ORDER, 1)]

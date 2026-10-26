"""What each step of the Tutorial screen shows: tutorial/resources/tutorial.yaml, with the solutions of the
notebooks (questions.yaml)."""

from html import escape
from pathlib import Path

import yaml
from form import script
from panels import (
    BLUE,
    BOX,
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

# this screen as it is (time, full screen, ...), at another step; links.js fills in ${__url...}
HERE = "${__url.path}${__url.params:exclude:var-step}&var-step="
CIRCLE = (
    "display:inline-flex;align-items:center;justify-content:center;width:30px;height:30px;"
    "border-radius:50%;font-size:16px;font-weight:500;text-decoration:none"
)
BUTTON = (
    f"padding:5px 16px;border:1px solid {LINE};border-radius:4px;color:{INK};font-size:16px;"
    "text-decoration:none"
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
            f'<div style="display:flex;gap:6px;margin-top:4px">{circles}</div></div>'
        )
    return f'<div style="display:flex;flex-wrap:wrap;gap:12px 36px">{"".join(groups)}</div>'


def button(step, label):
    return f'<a data-href="{HERE}{step}" style="{BUTTON}">{label}</a>'


def unfolds(name, label, shown, alone=False):
    """A button that shows or hides the hint, the solution, or what to change: `label` while it is hidden, `shown`
    while it shows (`alone`: on a line of its own)."""
    place = ";align-self:flex-start;margin-top:8px" if alone else ""
    data = f'data-show="{name}" data-folded="{label}" data-shown="{shown}"'
    return f'<a {data} style="{BUTTON};cursor:pointer{place}">{label}</a>'


def note(color, text, folded=""):
    """A box of text with a rule on its left, in a colour of meaning; `folded`: hidden until its button."""
    hidden = f' class="{folded}" hidden' if folded else ""
    return (
        f'<p{hidden} style="font-size:17px;margin:8px 0 0;padding:8px 14px;border-left:4px solid {color};'
        f'background:{BOX}">{text}</p>'
    )


# a choice: its letter in a circle, then its text, across the card
CHOICE = (
    f"display:flex;align-items:center;gap:12px;padding:2px 12px;border:1px solid {LINE};border-radius:4px;"
    f"color:{INK};font-size:16px;cursor:pointer"
)
LETTER = (
    f"display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;"
    f"border:1px solid {LINE};border-radius:50%;font-size:13px"
)


def choices(options, answer):
    """The choices of a question, A to D, one under the other; `answer`: the right one's letter."""
    rows = "".join(
        f'<a data-choice="{"right" if letter == answer else "wrong"}" '
        f'style="{CHOICE}"><span style="{LETTER}">{letter}</span>{escape(option)}</a>'
        for letter, option in zip("ABCD", options, strict=True)
    )
    return f'<div style="display:flex;flex-direction:column;gap:4px;margin-top:8px">{rows}</div>'


def card(n):
    """Step n as text: the steps, its question, what to change, and its choices; under them, its hint
    and its solution, folded until asked for; at the bottom, Hint and Solution, then Back and Next."""
    _, step = ORDER[n - 1]
    solution = step.get("solution", QUESTIONS[step["question"]]["solution"])
    lines = [
        navigator(n),
        f'<p style="font-size:20px;margin:12px 0 0">'
        f"<strong>Question {n}:</strong> {escape(step['ask'])}</p>",
    ]
    if "formula" in step:  # OpenDC's power model, for the steps on r
        lines.append(
            f'<p style="font-size:18px;margin:6px 0 0;font-family:serif">{step["formula"]}</p>'
        )
    if "do" in step:  # what to change on the twin, hidden until asked for
        lines += [
            unfolds("change", "Tell me what to change", "Hide what to change", alone=True),
            note(BLUE, f"<strong>Change:</strong> {escape(step['do'])}.", "change"),
        ]
    lines += [
        choices(step["choices"], step["answer"]),
        note(
            RED,
            "<strong>Not quite;</strong> look at what the plots show, then try another.",
            "retry",
        ),
        note(YELLOW, f"<strong>Hint:</strong> {escape(step['hint'])}", "hint"),
        note(GREEN, f"<strong>Solution:</strong> {escape(solution.strip())}", "solution"),
    ]
    left = [unfolds("hint", "Hint", "Hide hint"), unfolds("solution", "Solution", "Hide solution")]
    right = [
        button(i, label) for i, label in [(n - 1, "Back"), (n + 1, "Next")] if 1 <= i <= len(ORDER)
    ]
    # the buttons at the card's bottom, in the same place at every step
    lines.append(
        f'<div style="display:flex;gap:8px;margin-top:auto;padding-top:6px">{"".join(left)}'
        f'<div style="display:flex;gap:8px;margin-left:auto">{"".join(right)}</div></div>'
    )
    column = "display:flex;flex-direction:column;min-height:100%"
    content = f'<div style="{column}">' + "\n".join(lines) + "</div>"
    # late: yellow, darker on the light theme, as #F0E442 hardly shows on white
    colors = {"right": GREEN, "late": YELLOW, "late-light": "#998A00", "wrong": RED, "none": LINE}
    code = script(
        "links.js",
        "warn.js",
        "step.js",
        colors=colors,
        step=str(n),
        start=STARTS[n - 1],
        control=f"{BROWSER_API}/api/control",
        status=f"{BROWSER_API}/api/status",
    )
    return text(content, code)


# the values of the step variable, 1, 2, 3, ...: (value, step, card)
SLIDES = [(str(n), step, card(n)) for n, (_, step) in enumerate(ORDER, 1)]

"""What each step of the Tutorial screen shows: tutorial/resources/tutorial.yaml, with the solutions of the
notebooks (questions.yaml)."""

from html import escape
from pathlib import Path

import yaml
from form import script
from panels import BLUE, BOX, FAINT, GREEN, INK, LINE, RED, WHITE, YELLOW
from plots import ROWS, TILES, co2, hosts, power

RESOURCES = Path(__file__).resolve().parents[3] / "tutorial" / "resources"
STEPS = yaml.safe_load((RESOURCES / "tutorial.yaml").read_text())
QUESTIONS = yaml.safe_load((RESOURCES / "questions.yaml").read_text())
PLOTS = {"power": power, "co2": co2, "hosts": hosts, **TILES}
PLOTS |= {key: plot for plots in ROWS.values() for key, plot in plots.items()}
# step n is ORDER[n - 1]: (use case, step)
ORDER = [(use_case, step) for use_case, items in STEPS.items() for step in items]

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
    """Step n in a circle, as the steps of a figure: filled if current, else a link to step n."""
    if n == current:
        return f'<span style="{CIRCLE};background:{BLUE};color:{WHITE}">{n}</span>'
    return f'<a data-href="{HERE}{n}" style="{CIRCLE};border:1px solid {LINE};color:{INK}">{n}</a>'


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


def unfolds(name, label):
    """A button that unfolds the hint or the solution."""
    return f'<a data-show="{name}" style="{BUTTON};cursor:pointer">{label}</a>'


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
    """The choices of a question, A to D, one under the other; `answer`: the right one's letter (none: a
    guess)."""
    rows = "".join(
        f'<a data-choice="{"guess" if not answer else "right" if letter == answer else "wrong"}" '
        f'style="{CHOICE}"><span style="{LETTER}">{letter}</span>{escape(option)}</a>'
        for letter, option in zip("ABCD", options, strict=True)
    )
    return f'<div style="display:flex;flex-direction:column;gap:4px;margin-top:8px">{rows}</div>'


def card(n):
    """Step n as text: the steps, its question (on one line), what to change, and its choices; under them, its hint
    and its solution, folded until asked for; at the bottom, Hint and Solution, then Back and Next."""
    _, step = ORDER[n - 1]
    solution = step.get("solution", QUESTIONS[step["question"]].get("solution"))
    lines = [
        navigator(n),
        f'<p style="font-size:20px;margin:12px 0 0;white-space:nowrap">'
        f"<strong>Question {n}:</strong> {escape(step['ask'])}</p>",
    ]
    if "do" in step:
        lines.append(note(BLUE, f"<strong>Change:</strong> {escape(step['do'])}."))
    if "choices" in step:
        lines.append(choices(step["choices"], step.get("answer")))
    lines.append(note(YELLOW, f"<strong>Hint:</strong> {escape(step['hint'])}", "hint"))
    left = [unfolds("hint", "Hint")]
    if solution:
        lines.append(
            note(GREEN, f"<strong>Solution:</strong> {escape(solution.strip())}", "solution")
        )
        left.append(unfolds("solution", "Solution"))
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
    colors = {"right": GREEN, "wrong": RED, "guess": BLUE, "none": LINE}
    return {
        "type": "marcusolsson-dynamictext-panel",
        "title": "",
        "options": {
            "renderMode": "allRows",  # once, with or without data
            "content": content,
            "defaultContent": content,
            "afterRender": script("links.js", "step.js", colors=colors),
        },
    }


# the values of the step variable, 1, 2, 3, ...: (value, step, card)
SLIDES = [(str(n), step, card(n)) for n, (_, step) in enumerate(ORDER, 1)]

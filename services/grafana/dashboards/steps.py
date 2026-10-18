"""What each step of the Tutorial screen shows: tutorial/resources/tutorial.yaml, with the questions and
solutions of the notebooks (questions.yaml)."""

from html import escape
from pathlib import Path

import yaml
from panels import BLUE, BOX, FAINT, GREEN, INK, LINE, WHITE
from plots import ROWS, TILES, co2, hosts, power

RESOURCES = Path(__file__).resolve().parents[3] / "tutorial" / "resources"
STEPS = yaml.safe_load((RESOURCES / "tutorial.yaml").read_text())
QUESTIONS = yaml.safe_load((RESOURCES / "questions.yaml").read_text())
PLOTS = {"power": power, "co2": co2, "hosts": hosts, **TILES}
PLOTS |= {key: plot for plots in ROWS.values() for key, plot in plots.items()}
# step n is ORDER[n - 1]: (use case, step)
ORDER = [(use_case, step) for use_case, items in STEPS.items() for step in items]

# this screen as it is (time, full screen, ...), at another step; Grafana fills in ${__url...}
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
    return f'<a href="{HERE}{n}" style="{CIRCLE};border:1px solid {LINE};color:{INK}">{n}</a>'


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
    return f'<a href="{HERE}{step}" style="{BUTTON}">{label}</a>'


def note(color, text):
    """A box of text with a rule on its left, in a colour of meaning."""
    return (
        f'<p style="font-size:17px;margin:8px 0 0;padding:8px 14px;border-left:4px solid {color};'
        f'background:{BOX}">{text}</p>'
    )


def card(n, shown=False):
    """Step n as text: the steps, its question, and what to do in the control panel (`shown`: its
    solution instead); at the bottom, a button to show or fold the solution, then Back and Next."""
    _, step = ORDER[n - 1]
    q, question = step["question"], QUESTIONS[step["question"]]
    lines = [
        navigator(n),
        f'<p style="font-size:24px;color:{WHITE};margin:12px 0 0;max-width:1100px">'
        f"<strong>Question {q}:</strong> {escape(question['question'].strip())}</p>",
    ]
    if shown:
        solution = escape(question["solution"].strip())
        lines.append(note(GREEN, f"<strong>Solution {q}:</strong> {solution}"))
    elif "do" in step:
        lines.append(note(BLUE, f"<strong>In the control panel:</strong> {escape(step['do'])}."))
    left = []
    if "solution" in question:
        left = [button(n, "Hide solution") if shown else button(f"{n}s", "Solution")]
    right = [
        button(i, label) for i, label in [(n - 1, "Back"), (n + 1, "Next")] if 1 <= i <= len(ORDER)
    ]
    # the buttons at the card's bottom, in the same place at every step
    lines.append(
        f'<div style="display:flex;gap:8px;margin-top:auto;padding-top:6px">{"".join(left)}'
        f'<div style="display:flex;gap:8px;margin-left:auto">{"".join(right)}</div></div>'
    )
    column = "display:flex;flex-direction:column;height:100%"
    content = f'<div style="{column}">' + "\n".join(lines) + "</div>"
    return {"type": "text", "title": "", "options": {"mode": "html", "content": content}}


# the values of the step variable: n, step n, and ns, step n with its solution shown
SLIDES = []  # (value, step, card, shown)
for n, (_, step) in enumerate(ORDER, 1):
    SLIDES.append((str(n), step, card(n), False))
    if "solution" in QUESTIONS[step["question"]]:
        SLIDES.append((f"{n}s", step, card(n, shown=True), True))

"""What each step of the Tutorial screen shows: tutorial/resources/tutorial.yaml, with the questions and
solutions of the notebooks (questions.yaml)."""

from pathlib import Path

import yaml
from plots import ROWS, TILES, co2, hosts, power

RESOURCES = Path(__file__).resolve().parents[3] / "tutorial" / "resources"
STEPS = yaml.safe_load((RESOURCES / "tutorial.yaml").read_text())
QUESTIONS = yaml.safe_load((RESOURCES / "questions.yaml").read_text())
PLOTS = {"power": power, "co2": co2, "hosts": hosts, **TILES}
PLOTS |= {key: plot for plots in ROWS.values() for key, plot in plots.items()}


def text(title, step):
    """The step as text: the question, what to do in the control panel, and the solution, folded."""
    q = step["question"]
    lines = [f"**Question {q}:** {QUESTIONS[q]['question']}"]
    if "do" in step:
        lines.append(f"**In the control panel:** {step['do']}.")
    if step.get("solution", True) and "solution" in QUESTIONS[q]:
        solution = f"**Solution {q}:** {QUESTIONS[q]['solution']}"
        lines.append(f"<details><summary>Solution</summary>\n\n{solution}\n</details>")
    return {
        "type": "text",
        "title": title,
        "options": {"mode": "markdown", "content": "\n\n".join(lines)},
    }

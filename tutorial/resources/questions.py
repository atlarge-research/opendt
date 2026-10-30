"""The questions of the notebooks, from questions.yaml: a click on a choice says if it holds, and
the right one unfolds the solution."""

from __future__ import annotations

import re
from html import escape
from pathlib import Path

import yaml
from IPython.display import HTML, Markdown, display

QUESTIONS = Path(__file__).with_name("questions.yaml")


def ask_question(q: str) -> None:
    """Show question `q` (e.g., "1.2") and its choices, A to D, each folded on its verdict."""
    entry = yaml.safe_load(QUESTIONS.read_text())[q]
    display(Markdown(f"**Question {q}:** {entry['question']}"))
    display(HTML(choices(entry)))


def choices(entry: dict) -> str:
    """The choices; the right one unfolds the solution, and an experiment to explore."""
    lines = []
    for letter, choice in zip("ABCD", entry["choices"], strict=True):
        verdict = "<i>Not quite; look at what the cells print or plot, then try another.</i>"
        if entry["question"].startswith("Estimate"):  # asked before the cell that answers it
            verdict = "<i>Not quite; run the next cell, then try another.</i>"
        if letter == entry["answer"]:
            verdict = f"<i>Right.</i> {html(entry['solution'])}"
            if "explore" in entry:
                verdict += f"<br><i>Explore:</i> {html(entry['explore'])}"
        lines.append(
            f"<details><summary><b>{letter}.</b> {escape(choice)}</summary>{verdict}</details>"
        )
    return "".join(lines)


def html(text: str) -> str:
    """Text of questions.yaml in a fold, on one line as in Markdown: `code` as code, $P_{max}$ as
    P<sub>max</sub>, and $u^{r}$ as u<sup>r</sup>."""
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", escape(" ".join(text.split())))
    text = re.sub(r"\$(\w)_\{(\w+)\}\$", r"\1<sub>\2</sub>", text)
    return re.sub(r"\$(\w)\^\{(\w+)\}\$", r"\1<sup>\2</sup>", text)

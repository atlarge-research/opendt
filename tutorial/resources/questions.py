"""The questions of the notebooks and their solutions, from questions.yaml; a solution shows only on request."""

from __future__ import annotations

from html import escape
from pathlib import Path

import yaml
from IPython.display import HTML, Image, Markdown, display

QUESTIONS = Path(__file__).with_name("questions.yaml")


def ask_question(q: str) -> None:
    """Show question `q` (e.g., "1.2") and its choices, A to D: a click on one says if it holds."""
    entry = yaml.safe_load(QUESTIONS.read_text())[q]
    optional = " (optional)" if entry.get("optional") else ""
    display(Markdown(f"**Question {q}{optional}:** {entry['question']}"))
    display(HTML(choices(entry)))


def choices(entry: dict) -> str:
    """The choices, each folded on its verdict; without an answer, the question asks for a guess."""
    answer = entry.get("answer")
    lines = []
    for letter, choice in zip("ABCD", entry["choices"], strict=True):
        if not answer:
            verdict = "A guess; the next cells check it."
        elif letter == answer:
            verdict = "Right. Why? Think it through, then compare with the solution."
        else:
            verdict = "Not quite; look at what the cells print or plot, then try another."
        lines.append(
            f"<details><summary><b>{letter}.</b> {escape(choice)}</summary><i>{verdict}</i></details>"
        )
    return "".join(lines)


def give_solution(q: str, show: bool = False) -> None:
    """Show the solution of question `q`, only with show=True."""
    if not show:
        display(Markdown(f"*Solution {q}: set `show=True` in this cell and run it again.*"))
        return
    entry = yaml.safe_load(QUESTIONS.read_text())[q]
    right = f"({entry['answer']}) " if entry.get("answer") else ""
    display(Markdown(f"**Solution {q}:** {right}{entry['solution']}"))
    if "image" in entry:
        display(Image(filename=QUESTIONS.parent / entry["image"], width=700))
    if "explore" in entry:  # an experiment of their own, once the solution is known
        display(Markdown(f"*Explore:* {entry['explore']}"))

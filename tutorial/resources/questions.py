"""The questions of the notebooks and their solutions, from questions.yaml; a solution shows only on request."""

from __future__ import annotations

from pathlib import Path

import yaml
from IPython.display import Image, Markdown, display

QUESTIONS = Path(__file__).with_name("questions.yaml")


def ask_question(q: str) -> None:
    """Show question `q` (e.g., "1.2")."""
    entry = yaml.safe_load(QUESTIONS.read_text())[q]
    optional = " (optional)" if entry.get("optional") else ""
    display(Markdown(f"**Question {q}{optional}:** {entry['question']}"))


def give_solution(q: str, show: bool = False) -> None:
    """Show the solution of question `q`, only with show=True."""
    if not show:
        display(Markdown(f"*Solution {q}: set `show=True` in this cell and run it again.*"))
        return
    entry = yaml.safe_load(QUESTIONS.read_text())[q]
    display(Markdown(f"**Solution {q}:** {entry['solution']}"))
    if "image" in entry:
        display(Image(filename=QUESTIONS.parent / entry["image"], width=700))

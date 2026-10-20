"""Questions show on demand; a solution shows only with show=True."""

import json
import re

import yaml
from conftest import TUTORIAL_DIR
from resources import questions

CALLS = re.compile(r'(ask_question|give_solution)\("([^"]+)"')


def entries():
    return yaml.safe_load(questions.QUESTIONS.read_text())


def shown(monkeypatch, call):
    out = []
    monkeypatch.setattr(questions, "display", out.append)
    call()
    return " ".join(str(getattr(o, "data", o)) for o in out)


def test_solution_stays_hidden_until_asked_for(monkeypatch):
    solution = entries()["1.1"]["solution"].strip()
    assert solution not in shown(monkeypatch, lambda: questions.give_solution("1.1"))
    assert solution in shown(monkeypatch, lambda: questions.give_solution("1.1", show=True))


def test_ask_question_shows_the_question(monkeypatch):
    assert entries()["1.1"]["question"].strip() in shown(
        monkeypatch, lambda: questions.ask_question("1.1")
    )


def test_notebooks_and_questions_file_match():
    calls = set()
    for path in TUTORIAL_DIR.glob("[0-9].*.ipynb"):
        for cell in json.loads(path.read_text())["cells"]:
            if cell["cell_type"] == "code":
                calls |= set(CALLS.findall("".join(cell["source"])))
    assert {q for _, q in calls} == set(entries())
    assert all("solution" in entries()[q] for call, q in calls if call == "give_solution")


def test_solution_images_exist():
    images = [e["image"] for e in entries().values() if "image" in e]
    assert images and all((questions.QUESTIONS.parent / image).exists() for image in images)


def test_four_choices_each_answer_folded(monkeypatch):
    for q, entry in entries().items():
        assert len(entry["choices"]) == 4 and entry["answer"] in "ABCD" and entry["solution"], q
    shows = shown(monkeypatch, lambda: questions.ask_question("1.1"))
    assert (
        shows.count("<details>") == 4 and "Right" in shows
    )  # each choice says if it holds, once opened


def test_solution_names_the_right_choice(monkeypatch):
    assert "(B)" in shown(monkeypatch, lambda: questions.give_solution("1.1", show=True))


def test_explore_comes_with_the_solution(monkeypatch):
    explore = entries()["1.3"]["explore"]
    assert explore not in shown(monkeypatch, lambda: questions.ask_question("1.3"))
    assert explore in shown(monkeypatch, lambda: questions.give_solution("1.3", show=True))

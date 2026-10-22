"""Questions and their choices: a click on a choice says if it holds, and the right one unfolds the
solution."""

import json
import re

import yaml
from conftest import TUTORIAL_DIR
from resources import questions

ASKED = re.compile(r'ask_question\("([^"]+)"')


def entries():
    return yaml.safe_load(questions.QUESTIONS.read_text())


def shown(monkeypatch, call):
    out = []
    monkeypatch.setattr(questions, "display", out.append)
    call()
    return " ".join(str(getattr(o, "data", o)) for o in out)


def folds(monkeypatch, q):
    """What each choice of question `q` unfolds, by its letter."""
    shows = shown(monkeypatch, lambda: questions.ask_question(q))
    return dict(re.findall(r"<details><summary><b>(\w)\.</b>.*?</summary>(.*?)</details>", shows))


def test_ask_question_shows_the_question(monkeypatch):
    assert entries()["1.1"]["question"].strip() in shown(
        monkeypatch, lambda: questions.ask_question("1.1")
    )


def test_notebooks_and_questions_file_match():
    asked = set()
    for path in TUTORIAL_DIR.glob("[0-9].*.ipynb"):
        for cell in json.loads(path.read_text())["cells"]:
            if cell["cell_type"] == "code":
                asked |= set(ASKED.findall("".join(cell["source"])))
    assert asked == set(entries())


def test_solution_images_exist():
    images = [e["image"] for e in entries().values() if "image" in e]
    assert all((questions.QUESTIONS.parent / image).exists() for image in images)


def test_four_choices_each_answer_folded(monkeypatch):
    for q, entry in entries().items():
        assert len(entry["choices"]) == 4 and entry["answer"] in "ABCD" and entry["solution"], q
    assert list(folds(monkeypatch, "1.1")) == list("ABCD")


def test_the_right_choice_unfolds_the_solution(monkeypatch):
    solution = questions.html(entries()["1.1"]["solution"])
    shows = folds(monkeypatch, "1.1")
    assert solution in shows["B"] and "Right" in shows["B"]
    assert all(solution not in shows[letter] for letter in "ACD")


def test_explore_comes_with_the_solution(monkeypatch):
    explore = questions.html(entries()["1.3"]["explore"])
    assert explore in folds(monkeypatch, "1.3")["C"]


def test_code_and_symbols_in_a_fold():
    assert questions.html("try `SPARE = 0`") == "try <code>SPARE = 0</code>"
    assert questions.html("exceeds $P_{max}$") == "exceeds P<sub>max</sub>"

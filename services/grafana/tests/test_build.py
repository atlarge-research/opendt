"""The screens: the provisioned JSON is what dashboards/ writes (change a plot there, run build.py)."""

import re

import build
import screens
import steps


def test_dashboards_are_built(tmp_path):
    build.write(tmp_path)
    for path in build.DASHBOARDS:
        assert (tmp_path / path).read_text() == (build.OUT / path).read_text(), (
            f"{path}: run build.py"
        )


def test_plots_show_until_hidden():
    spec = screens.detailed["spec"]
    [hidden] = [v["spec"] for v in spec["variables"] if v["spec"]["name"] == "hidden"]
    pickable = [key for _, plots in screens.ROW_PLOTS for key, _ in plots]
    items = [
        item["spec"]
        for row in spec["layout"]["spec"]["rows"]
        if row["spec"]["layout"]["kind"] == "AutoGridLayout" and row["spec"]["title"]
        for item in row["spec"]["layout"]["spec"]["items"]
    ]
    assert hidden["query"].split(",") == ["none", *pickable]
    assert [item["element"]["name"] for item in items] == pickable
    # the address keeps the hidden plots, so a plot added later shows, even with an old address
    assert hidden["current"]["value"] == ["none"]
    for item in items:
        [rule] = item["conditionalRendering"]["spec"]["items"]
        assert rule["spec"] == {
            "variable": "hidden",
            "operator": "notEquals",
            "value": item["element"]["name"],
        }


def test_steps_are_known():
    for use_case in steps.STEPS.values():
        for step in use_case:
            assert step["question"] in steps.QUESTIONS
            assert set(step["plots"]) <= steps.PLOTS.keys()


def test_one_step_at_a_time():
    spec = screens.tutorial["spec"]
    [step] = [v["spec"] for v in spec["variables"] if v["spec"]["name"] == "step"]
    rows = {
        r["spec"]["conditionalRendering"]["spec"]["items"][0]["spec"]["value"]: r["spec"]
        for r in spec["layout"]["spec"]["rows"][1:]  # after the start's
    }
    assert step["query"].split(",") == list(rows)  # a row for each value of the step
    for n, (_, s) in enumerate(steps.ORDER, 1):
        names = [i["spec"]["element"]["name"] for i in rows[str(n)]["layout"]["spec"]["items"]]
        assert {"control", f"step-{n}", *screens.BOXES} <= set(names)
        plots = [name.removeprefix("plot-") for name in names if name.startswith("plot-")]
        assert plots == s["plots"]


def test_card():
    last = len(steps.ORDER)
    for n, (_, step) in enumerate(steps.ORDER, 1):
        card = steps.card(n)["options"]["content"]
        linked = {int(i) for i in re.findall(r'var-step=(\d+)"', card)}
        assert linked == set(range(1, last + 1)) - {n}  # every other step
        assert f"Question {n}:</strong>" in card and len(step["ask"]) <= 95  # on one line
        assert (
            '<p class="hint" hidden' in card
        )  # every question has a hint, folded like the solution
        assert step.get("answer", 1) in range(1, len(step.get("choices", [1])) + 1)
    assert ">Back<" not in steps.card(1)["options"]["content"]
    assert ">Next<" not in steps.card(last)["options"]["content"]
    middle = steps.card(2)["options"]["content"]
    assert middle.index(">Back<") < middle.index(">Next<")


def test_split():
    assert screens.split(["a"], 6, 9, 18, 14) == [("a", 6, 9, 18, 14)]
    assert screens.split(["a", "b"], 6, 9, 18, 14) == [("a", 6, 9, 9, 14), ("b", 15, 9, 9, 14)]
    # top to bottom, then left to right; of three, the first is as tall as the area
    three = [("a", 6, 9, 9, 14), ("b", 15, 9, 9, 7), ("c", 15, 16, 9, 7)]
    assert screens.split(["a", "b", "c"], 6, 9, 18, 14) == three
    four = [("a", 6, 9, 9, 7), ("b", 6, 16, 9, 7), ("c", 15, 9, 9, 7), ("d", 15, 16, 9, 7)]
    assert screens.split(["a", "b", "c", "d"], 6, 9, 18, 14) == four
    # down to the bottom, the lower plot taller by what does not divide
    assert screens.split(["a", "b", "c"], 6, 9, 18, 13)[1:] == [
        ("b", 15, 9, 9, 6),
        ("c", 15, 15, 9, 7),
    ]


def test_tutorial_starts_on_day():
    def window(board):
        [time] = [v["spec"] for v in board["spec"]["variables"] if v["spec"]["name"] == "window"]
        code = board["spec"]["elements"]["control"]["spec"]["vizConfig"]["spec"]["options"][
            "initial"
        ]
        assert "'${window}'" in code["code"]  # the control panel takes it from the address
        return time["current"]["value"]

    assert window(screens.tutorial) == "day"
    assert window(screens.detailed) == window(screens.simple) == "week"


def test_starting_first():
    # while the twin starts, what it does is the first thing on every screen
    for board in (screens.detailed, screens.simple, screens.topology, screens.tutorial):
        [first, *_] = board["spec"]["layout"]["spec"]["rows"]
        items = first["spec"]["layout"]["spec"]["items"]
        assert [i["spec"]["element"]["name"] for i in items] == list(screens.STARTING)

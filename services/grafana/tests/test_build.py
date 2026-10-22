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
    shown = {k for row, plots in screens.ROWS.items() if row in screens.SHOWN for k in plots}
    assert hidden["current"]["value"] == ["none", *(k for k in pickable if k not in shown)]
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
            assert set(step.get("plots", [])) <= steps.PLOTS.keys()
            assert {*step.get("set", {}), *step.get("start", {})} <= {*steps.BASE}  # what the twin's API takes


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
        assert {"brand", f"step-{n}", *screens.BOXES} <= set(names)
        plots = [name.removeprefix("plot-") for name in names if name.startswith("plot-")]
        assert plots == s.get("plots", [])
        assert (f"figure-{n}" in names) == ("figure" in s)


def test_card():
    last = len(steps.ORDER)
    for n, (_, step) in enumerate(steps.ORDER, 1):
        card = steps.card(n)["options"]["content"]
        linked = {int(i) for i in re.findall(r'var-step=(\d+)"', card)}
        assert linked == set(range(1, last + 1)) - {n}  # every other step
        assert f"Question {n}:</strong>" in card and len(step["ask"]) <= 95  # on one line
        # each step alike: four choices, the right one; a hint and a solution, folded; what to change, if any, too
        assert len(step["choices"]) == 4 and step["answer"] in "ABCD"
        assert '<p class="hint" hidden' in card and '<p class="solution" hidden' in card
        assert ("do" in step) == ('<p class="change" hidden' in card)
    assert ">Back<" not in steps.card(1)["options"]["content"]
    assert ">Next<" not in steps.card(last)["options"]["content"]
    middle = steps.card(2)["options"]["content"]
    assert middle.index(">Back<") < middle.index(">Next<")


def test_side_by_side():
    assert screens.side_by_side(["a"], 6, 9, 18, 8) == [("a", 6, 9, 18, 8)]
    assert screens.side_by_side(["a", "b"], 6, 9, 18, 8) == [("a", 6, 9, 9, 8), ("b", 15, 9, 9, 8)]
    # the last ones wider by what does not divide
    four = [("a", 6, 9, 4, 8), ("b", 10, 9, 5, 8), ("c", 15, 9, 4, 8), ("d", 19, 9, 5, 8)]
    assert screens.side_by_side(["a", "b", "c", "d"], 6, 9, 18, 8) == four


def test_tutorial_starts_on_day():
    def window(board):
        [time] = [v["spec"] for v in board["spec"]["variables"] if v["spec"]["name"] == "window"]
        view = board["spec"]["elements"]["brand"]["spec"]["vizConfig"]["spec"]["options"]
        assert 'data-var="window"' in view["content"]  # the view shows it, from the address
        return time["current"]["value"]

    assert window(screens.tutorial) == "day"
    assert window(screens.detailed) == window(screens.topology) == "week"


def test_starting_first():
    # while the twin starts, what it does is the first thing on every screen
    for board in (screens.detailed, screens.topology, screens.tutorial):
        [first, *_] = board["spec"]["layout"]["spec"]["rows"]
        items = first["spec"]["layout"]["spec"]["items"]
        assert [i["spec"]["element"]["name"] for i in items] == list(screens.STARTING)

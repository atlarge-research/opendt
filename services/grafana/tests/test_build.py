"""The screens: the provisioned JSON is what dashboards/ writes (change a plot there, run build.py)."""

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
    pickable = [
        o["value"]
        for name, e in spec["elements"].items()
        if name.startswith("pick-")
        for o in e["spec"]["vizConfig"]["spec"]["options"]["elements"][0]["options"]
    ]
    items = [
        item["spec"]
        for row in spec["layout"]["spec"]["rows"]
        if row["spec"]["layout"]["kind"] == "AutoGridLayout"
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
    count = sum(len(use_case) for use_case in steps.STEPS.values())
    assert step["query"].split(",") == [str(n) for n in range(1, count + 1)]
    [area] = [
        r["spec"]["layout"]["spec"]["items"]
        for r in spec["layout"]["spec"]["rows"]
        if r["spec"]["title"] == "Step"
    ]
    texts = [item["spec"] for item in area if item["spec"]["element"]["name"].startswith("text-")]
    for n, text in enumerate(texts, 1):
        [rule] = text["conditionalRendering"]["spec"]["items"]
        assert rule["spec"] == {"variable": "step", "operator": "equals", "value": str(n)}

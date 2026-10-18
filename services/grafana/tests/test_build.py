"""The screens: the provisioned JSON is what dashboards/ writes (change a plot there, run build.py)."""

import build
import screens


def test_the_provisioned_dashboards_are_built_from_the_code(tmp_path):
    build.write(tmp_path)
    for path in build.DASHBOARDS:
        assert (tmp_path / path).read_text() == (build.OUT / path).read_text(), (
            f"{path}: run build.py"
        )


def test_every_plot_can_be_picked_and_shows_until_hidden():
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

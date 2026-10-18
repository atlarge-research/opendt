"""The provisioned dashboards are what dashboards/ writes: change a plot there, then run build.py."""

import build


def test_the_provisioned_dashboards_are_built_from_the_code(tmp_path):
    build.write(tmp_path)
    for path in build.DASHBOARDS:
        assert (tmp_path / path).read_text() == (build.OUT / path).read_text(), (
            f"{path}: run build.py"
        )

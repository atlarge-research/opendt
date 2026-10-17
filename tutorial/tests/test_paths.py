"""Tests for repository discovery and the setup check."""

import pytest
from conftest import REPO

from opendt_tutorial import paths
from opendt_tutorial.paths import PATHS, SetupError, check_setup, repo_root


def test_repo_root_from_any_cwd(tmp_path, monkeypatch):
    for cwd in (REPO / "tutorial", REPO, REPO / "tutorial" / "tests"):
        monkeypatch.chdir(cwd)
        assert repo_root() == REPO
    with pytest.raises(SetupError):
        repo_root(start=tmp_path)


def test_paths_point_into_the_repo():
    assert PATHS.root == REPO
    assert PATHS.opendc_bin == REPO / "opendc/bin/OpenDCExperimentRunner/bin/OpenDCExperimentRunner"
    assert PATHS.workload == REPO / "workload/SURF"
    assert PATHS.output == REPO / "tutorial/output"


def test_check_setup_reports_wrong_java(monkeypatch):
    monkeypatch.setattr(paths, "_java_version", lambda: "17.0.2")
    with pytest.raises(SetupError, match="Java 21"):
        check_setup(verbose=False)


def test_check_setup_reports_missing_java(monkeypatch):
    monkeypatch.setattr(paths, "_java_version", lambda: None)
    with pytest.raises(SetupError, match="Java 21"):
        check_setup(verbose=False)


def test_check_setup_accepts_newer_java(monkeypatch):
    monkeypatch.setattr(paths, "_java_version", lambda: "23.0.1")
    check_setup(verbose=False)


@pytest.mark.opendc
def test_check_setup_passes_on_a_complete_machine(capsys):
    check_setup()
    out = capsys.readouterr().out
    assert "❌" not in out and out.count("✅") >= 4

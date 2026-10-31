"""Tests for repository discovery and the setup check."""

import pytest
from conftest import REPO
from resources import paths
from resources.paths import check_setup, repo_root


def test_repo_root_does_not_depend_on_the_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert repo_root() == REPO
    with pytest.raises(RuntimeError):
        repo_root(start=tmp_path)


@pytest.mark.parametrize("version", ["17.0.2", "1.8.0_292", None])
def test_without_java_21_the_precomputed_simulations_run(monkeypatch, capsys, version):
    monkeypatch.setattr(paths, "java_version", lambda: version)
    check_setup()
    shown = capsys.readouterr().out
    assert shown.startswith("Setup OK") and "precomputed" in shown and "need Java 21" in shown


def test_check_setup_accepts_newer_java(monkeypatch, capsys):
    monkeypatch.setattr(paths, "java_version", lambda: "23.0.1")
    check_setup()
    assert "Java 23.0.1" in capsys.readouterr().out


@pytest.mark.opendc
def test_check_setup_passes_on_a_complete_machine(capsys):
    check_setup()
    assert "runs on OpenDC with Java" in capsys.readouterr().out

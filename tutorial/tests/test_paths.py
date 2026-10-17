"""Tests for repository discovery and the setup check."""

import pytest
from conftest import REPO
from opendt_tutorial import paths
from opendt_tutorial.paths import check_setup, repo_root


def test_repo_root_does_not_depend_on_the_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert repo_root() == REPO
    with pytest.raises(RuntimeError):
        repo_root(start=tmp_path)


@pytest.mark.parametrize("version", ["17.0.2", "1.8.0_292", None])
def test_check_setup_rejects_old_or_missing_java(monkeypatch, version):
    monkeypatch.setattr(paths, "_java_version", lambda: version)
    with pytest.raises(RuntimeError, match="Java 21"):
        check_setup()


def test_check_setup_accepts_newer_java(monkeypatch, capsys):
    monkeypatch.setattr(paths, "_java_version", lambda: "23.0.1")
    check_setup()
    assert capsys.readouterr().out.startswith("Setup OK")


@pytest.mark.opendc
def test_check_setup_passes_on_a_complete_machine(capsys):
    check_setup()
    assert "Java 2" in capsys.readouterr().out

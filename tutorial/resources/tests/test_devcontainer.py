"""The Codespaces setup must at least parse; Task-12's container run checks that it works."""

import json
import subprocess

from conftest import REPO


def test_devcontainer_is_valid_json():
    config = json.loads((REPO / ".devcontainer/devcontainer.json").read_text())
    assert config["postCreateCommand"] == "bash .devcontainer/postCreate.sh"


def test_post_create_script_parses():
    assert subprocess.run(["bash", "-n", str(REPO / ".devcontainer/postCreate.sh")]).returncode == 0

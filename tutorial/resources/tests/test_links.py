"""Every link in the README, the run-sheet, and the notebooks points to something that exists."""

import re
import urllib.request

import nbformat
import pytest
from conftest import TUTORIAL_DIR

LINK = re.compile(r"\]\(([^)\s]+)\)")  # [text](target) and ![image](target)


def documents():
    """(folder the links are relative to, markdown text) of every document students read."""
    yield TUTORIAL_DIR, (TUTORIAL_DIR / "README.md").read_text()
    yield TUTORIAL_DIR / "resources", (TUTORIAL_DIR / "resources/INSTRUCTOR.md").read_text()
    for path in sorted(TUTORIAL_DIR.glob("*.ipynb")):
        notebook = nbformat.read(path, as_version=4)
        yield TUTORIAL_DIR, "\n".join(c.source for c in notebook.cells if c.cell_type == "markdown")


def links():
    return [(folder, target) for folder, text in documents() for target in LINK.findall(text)]


def test_relative_links_exist():
    missing = [
        target
        for folder, target in links()
        if not target.startswith(("http", "#")) and not (folder / target.split("#")[0]).exists()
    ]
    assert missing == []


@pytest.mark.network
def test_docs_links_are_live():
    docs = sorted(
        {t for _, t in links() if t.startswith("https://atlarge-research.github.io/opendt")}
    )
    for url in docs:
        with urllib.request.urlopen(url, timeout=30) as response:
            assert response.status == 200, url

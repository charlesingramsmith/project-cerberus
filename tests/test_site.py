"""Checks for the Derlin landing page (site/index.html, built by scripts/build_site.py)."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build_site  # noqa: E402

PAGE = (ROOT / "site" / "index.html").read_text(encoding="utf-8")


def test_page_is_built_from_the_template():
    # If this fails, run: python scripts/build_site.py
    assert PAGE == build_site.build()


def test_open_the_app_buttons_go_to_the_live_app():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert build_site.APP_URL in readme
    assert PAGE.count(f'href="{build_site.APP_URL}"') == 2


def test_page_uses_no_emoji():
    emoji = re.compile("[\U0001F300-\U0001FAFF☀-➿⭐⬆↔-↪]")
    assert not emoji.findall(PAGE)


def test_page_loads_no_scripts_and_its_files_exist():
    assert "<script" not in PAGE
    for ref in re.findall(r'href="([^":]+)"', PAGE):
        assert (ROOT / "site" / ref).exists(), ref

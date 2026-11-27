"""Checks for the Derlin website (the site/ folder, built by scripts/build_site.py)."""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build_site  # noqa: E402

PAGES = build_site.build()


@pytest.mark.parametrize("path", PAGES)
def test_pages_are_built_from_their_templates(path):
    # If this fails, run: python scripts/build_site.py
    assert (ROOT / "site" / path).read_text(encoding="utf-8") == PAGES[path]


def test_open_the_app_buttons_go_to_the_live_app():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert build_site.APP_URL in readme
    assert PAGES["index.html"].count(f'href="{build_site.APP_URL}"') == 2


@pytest.mark.parametrize("path", PAGES)
def test_pages_use_no_emoji_or_scripts(path):
    emoji = re.compile("[\U0001F300-\U0001FAFF☀-➿⭐]")
    assert not emoji.findall(PAGES[path])
    assert "<script" not in PAGES[path]


@pytest.mark.parametrize("path", PAGES)
def test_links_to_our_own_files_work(path):
    folder = (ROOT / "site" / path).parent
    for ref in re.findall(r'href="([^":#]+)"', PAGES[path]):
        target = (folder / ref).resolve()
        assert target.exists() and (target.is_file() or (target / "index.html").exists()), ref


def test_legal_pages_keep_the_whole_text():
    for name in build_site.LEGAL_PAGES:
        markdown = (ROOT / "legal" / f"{name}.md").read_text(encoding="utf-8")
        page = PAGES[f"{name}/index.html"]
        headings = re.findall(r"^#+ (.+)$", markdown, flags=re.M)
        assert headings and all(f">{h}</h" in page for h in headings)
        assert "**" not in page and "<strong>" in page


def test_markdown_to_html_escapes_and_handles_lists():
    html = build_site.markdown_to_html("# Hi\n\nA <b> & **bold**\n\n- one\n- two\n\n1. first\n2. second")
    assert html == ("<h1>Hi</h1>\n<p>A &lt;b&gt; &amp; <strong>bold</strong></p>\n"
                    "<ul>\n<li>one</li>\n<li>two</li>\n</ul>\n<ol>\n<li>first</li>\n<li>second</li>\n</ol>")

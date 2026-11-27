"""Build the Derlin landing page (site/index.html) from scripts/landing_page.html.

The template uses the app's own drawings, so the page and the app always match:
  {{logo}}          the pencil-sketch dachshund (assets/logo.svg)
  {{icon:<name>}}   a hand-drawn icon from cerberus/sketches.py
  {{app_url}}       the address of the app

Run from the repo root after changing the template, the logo or an icon:
    python scripts/build_site.py
GitHub Pages publishes the site/ folder (.github/workflows/pages.yml).
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cerberus import sketches  # noqa: E402

APP_URL = "https://project-cerberus.streamlit.app"
TEMPLATE = ROOT / "scripts" / "landing_page.html"
OUTPUT = ROOT / "site" / "index.html"


def logo_svg() -> str:
    """The logo without its own colour style: the page's --ink and --plum colour it."""
    drawing = (ROOT / "assets" / "logo.svg").read_text(encoding="utf-8")
    drawing = re.sub(r"<style>.*?</style>\s*", "", drawing, flags=re.S)
    drawing = re.sub(r"<!--.*?-->\s*", "", drawing, flags=re.S)
    return drawing.replace("<svg ", '<svg class="logo" ', 1).strip()


def build() -> str:
    page = TEMPLATE.read_text(encoding="utf-8")
    page = re.sub(r"<!-- Template for.*?-->\n", "", page, count=1, flags=re.S)
    page = page.replace("{{logo}}", logo_svg()).replace("{{app_url}}", APP_URL)
    page = re.sub(r"\{\{icon:(\w+)\}\}", lambda m: sketches.svg(m.group(1)), page)
    leftover = re.findall(r"\{\{.*?\}\}", page)
    if leftover:
        raise ValueError(f"Unknown placeholders in the template: {leftover}")
    return page


if __name__ == "__main__":
    OUTPUT.write_text(build(), encoding="utf-8", newline="\n")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")

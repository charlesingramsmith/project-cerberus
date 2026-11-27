"""Build the Derlin website (the site/ folder) from templates.

  site/index.html          from scripts/landing_page.html
  site/privacy/index.html  from legal/privacy.md, in scripts/legal_page.html
  site/terms/index.html    from legal/terms.md, in scripts/legal_page.html

The templates use the app's own drawings, so the site and the app always match:
  {{logo}}          the pencil-sketch dachshund (assets/logo.svg)
  {{icon:<name>}}   a hand-drawn icon from cerberus/sketches.py
  {{app_url}}       the address of the app
Styles live in site/style.css (edited by hand).

Run from the repo root after changing a template, the legal text, the logo or an icon:
    python scripts/build_site.py
GitHub Pages publishes the site/ folder (.github/workflows/pages.yml).
"""

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cerberus import sketches  # noqa: E402

APP_URL = "https://project-cerberus.streamlit.app"
SITE = ROOT / "site"
LEGAL_PAGES = {"privacy": "Privacy policy", "terms": "Terms of use"}


def logo_svg() -> str:
    """The logo without its own colour style: the page's --ink and --plum colour it."""
    drawing = (ROOT / "assets" / "logo.svg").read_text(encoding="utf-8")
    drawing = re.sub(r"<style>.*?</style>\s*", "", drawing, flags=re.S)
    drawing = re.sub(r"<!--.*?-->\s*", "", drawing, flags=re.S)
    return drawing.replace("<svg ", '<svg class="logo" ', 1).strip()


def inline(text: str) -> str:
    """Escape one line of Markdown text, then turn **bold** into <strong>."""
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html.escape(text, quote=False))


def markdown_to_html(text: str) -> str:
    """The small part of Markdown the legal pages use: #, ## and ### headings, paragraphs,
    "- " and "1. " lists, and **bold**. Anything else is shown as plain text."""
    out, paragraph, list_tag = [], [], None

    def close_paragraph():
        if paragraph:
            out.append(f"<p>{inline(' '.join(paragraph))}</p>")
            paragraph.clear()

    def close_list():
        nonlocal list_tag
        if list_tag:
            out.append(f"</{list_tag}>")
            list_tag = None

    for line in text.splitlines():
        line = line.rstrip()
        heading = re.match(r"(#{1,3}) (.+)", line)
        item = re.match(r"(-|\d+\.) (.+)", line)
        if not line:
            close_paragraph()
            close_list()
        elif heading:
            close_paragraph()
            close_list()
            level = len(heading.group(1))
            out.append(f"<h{level}>{inline(heading.group(2))}</h{level}>")
        elif item:
            close_paragraph()
            tag = "ul" if item.group(1) == "-" else "ol"
            if list_tag != tag:
                close_list()
                out.append(f"<{tag}>")
                list_tag = tag
            out.append(f"<li>{inline(item.group(2))}</li>")
        elif list_tag:  # a list item running on to the next line
            out[-1] = out[-1][: -len("</li>")] + " " + inline(line) + "</li>"
        else:
            paragraph.append(line)
    close_paragraph()
    close_list()
    return "\n".join(out)


def fill(template: str, **values: str) -> str:
    page = re.sub(r"<!-- Template for.*?-->\n", "", template, count=1, flags=re.S)
    values = {"logo": logo_svg(), "app_url": APP_URL, **values}
    page = re.sub(r"\{\{(\w+)\}\}", lambda m: values.get(m.group(1), m.group(0)), page)
    page = re.sub(r"\{\{icon:(\w+)\}\}", lambda m: sketches.svg(m.group(1)), page)
    leftover = re.findall(r"\{\{.*?\}\}", page)
    if leftover:
        raise ValueError(f"Unknown placeholders in a template: {leftover}")
    return page


def build() -> dict[str, str]:
    """Every page of the site, keyed by its path inside site/."""
    scripts = ROOT / "scripts"
    pages = {"index.html": fill((scripts / "landing_page.html").read_text(encoding="utf-8"))}
    legal_template = (scripts / "legal_page.html").read_text(encoding="utf-8")
    for name, title in LEGAL_PAGES.items():
        text = (ROOT / "legal" / f"{name}.md").read_text(encoding="utf-8")
        pages[f"{name}/index.html"] = fill(legal_template, title=title, body=markdown_to_html(text))
    return pages


if __name__ == "__main__":
    for path, page in build().items():
        target = SITE / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page, encoding="utf-8", newline="\n")
        print(f"Wrote {target.relative_to(ROOT)}")

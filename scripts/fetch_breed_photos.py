"""Find a free-licensed photo for every breed and save it to data/breed_photos.csv.

Run once by hand when breeds change (the app never runs this; it only reads the CSV):

    .venv/Scripts/python.exe scripts/fetch_breed_photos.py

For each breed it asks Wikipedia for the article's main picture (only freely licensed
images), then asks Wikimedia Commons for a 640px-wide copy plus the photographer and
licence, so the app can credit each photo properly.
"""
from __future__ import annotations

import csv
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from cerberus.logic import BREED_PHOTOS_CSV, load_breeds  # noqa: E402

USER_AGENT = "ProjectCerberus/1.0 (breed photo lookup script)"
WIDTH = 640

# Wikipedia article titles that differ from the AKC breed name.
ARTICLE = {
    "Boxer": "Boxer (dog breed)",
    "Poodle": "Poodle",
    "Bulldog": "Bulldog",
    "Mastiff": "English Mastiff",
    "Collie": "Rough Collie",
    "Brittany": "Brittany dog",
    "Akita": "American Akita",
    "Papillon": "Papillon dog",
    "Maltese": "Maltese dog",
    "Havanese": "Havanese dog",
    "Samoyed": "Samoyed dog",
    "Pug": "Pug",
    "Russell Terrier": "Jack Russell Terrier",
    "Cocker Spaniel": "American Cocker Spaniel",
    "Miniature American Shepherd": "Miniature American Shepherd",
    "Chinese Shar-Pei": "Shar Pei",
    "Bull Terrier": "Bull Terrier",
    "Doberman Pinscher": "Dobermann",
    "German Shepherd Dog": "German Shepherd",
    "Great Pyrenees": "Great Pyrenees",
    "Newfoundland": "Newfoundland dog",
    "Keeshond": "Keeshond",
    "Biewer Terrier": "Biewer Terrier",
    "Pomeranian": "Pomeranian dog",
    "Chihuahua": "Chihuahua (dog)",
    "Dalmatian": "Dalmatian dog",
    "Saint Bernard": "St. Bernard (dog)",
}

# Hand-picked photos where the article's main picture shows several dogs.
PHOTO = {
    "Belgian Malinois": "Malinois Shepherd3.JPG",
    "Akita": "Akita female.png",
}


def get_json(url: str, params: dict) -> dict:
    req = urllib.request.Request(f"{url}?{urllib.parse.urlencode(params)}",
                                 headers={"User-Agent": USER_AGENT})
    for wait in (5, 15, 45, None):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as err:
            if err.code != 429 or wait is None:
                raise
            time.sleep(wait)  # "too many requests": wait, then try again


def plain(text: str) -> str:
    """Commons metadata is HTML ("<a href=...>Name</a>"); keep just the words."""
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", text or "")).split())


def short_credit(artist: str) -> str:
    """Just the photographer's name: drop links, notes in brackets and long extras."""
    name = re.split(r" \(| https?://|, https?://|\. The original", artist)[0].strip(" ,;.")
    name = re.sub(r"^by ", "", name)
    if " : " in name:  # "Original.jpg : Photographer derivative work: Editor"
        name = name.split(" : ", 1)[1].split(" derivative work")[0].strip('" ')
    name = re.sub(r"@\S+", "", name)  # never show email addresses
    name = name.strip(" ,;.")
    return name if len(name) <= 60 else name[:57].rstrip() + "..."


def chunks(items: list, size: int = 50):
    """The APIs accept up to 50 titles per request."""
    for i in range(0, len(items), size):
        yield items[i:i + size]


def page_images(titles: list[str]) -> dict[str, str]:
    """{requested article title: file name of its main free image}."""
    found = {}
    for batch in chunks(titles):
        data = get_json("https://en.wikipedia.org/w/api.php", {
            "action": "query", "prop": "pageimages", "piprop": "name",
            "titles": "|".join(batch), "redirects": 1, "pilimit": 50, "format": "json",
        })["query"]
        # Map each requested title through any normalising/redirects to its final page.
        final = {t: t for t in batch}
        for step in ("normalized", "redirects"):
            hops = {h["from"]: h["to"] for h in data.get(step, [])}
            final = {t: hops.get(f, f) for t, f in final.items()}
        images = {p["title"]: p.get("pageimage") for p in data["pages"].values()}
        for title, page in final.items():
            if not images.get(page):
                raise LookupError(f"no free image on Wikipedia article {title!r} ({page!r})")
            found[title] = images[page]
        time.sleep(1)
    return found


def image_details(file_names: list[str]) -> dict[str, dict]:
    """{file name: image_url, credit, licence, source}."""
    details = {}
    for batch in chunks(file_names):
        data = get_json("https://commons.wikimedia.org/w/api.php", {
            "action": "query", "prop": "imageinfo", "iiprop": "url|extmetadata",
            "iiurlwidth": WIDTH, "titles": "|".join(f"File:{n}" for n in batch),
            "format": "json",
        })["query"]
        norm = {h["to"]: h["from"] for h in data.get("normalized", [])}
        for page in data["pages"].values():
            info = page["imageinfo"][0]
            meta = info["extmetadata"]
            name = norm.get(page["title"], page["title"]).removeprefix("File:")
            details[name] = {
                "image_url": (info.get("thumburl") or info["url"]).split("?")[0],  # drop tracking
                "credit": short_credit(plain(meta.get("Artist", {}).get("value", ""))) or "Unknown",
                "licence": plain(meta.get("LicenseShortName", {}).get("value", "")),
                "source": info["descriptionurl"],
            }
        time.sleep(1)
    return details


def main() -> None:
    breeds = list(load_breeds()["breed"])
    titles = [ARTICLE.get(b, b) for b in breeds]
    files = page_images(titles)
    files.update({ARTICLE.get(b, b): name for b, name in PHOTO.items()})
    details = image_details(sorted(set(files.values())))
    rows = []
    for breed, title in zip(breeds, titles):
        name = files[title]
        found = details.get(name) or details.get(name.replace("_", " "))
        rows.append({"breed": breed, **found})
        print(f"{breed:36} {found['licence']:16} {name}")
    with BREED_PHOTOS_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["breed", "image_url", "credit", "licence", "source"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {len(rows)} photos to {BREED_PHOTOS_CSV.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

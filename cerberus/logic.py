"""Pure life-list logic: no database, no Streamlit, easy to test.

A "lifer" is the first time a spotter logs a given breed.
"""
from __future__ import annotations

import io
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
BREEDS_CSV = ROOT / "data" / "breeds.csv"
CHANGELOG_MD = ROOT / "CHANGELOG.md"
ROADMAP_MD = ROOT / "ROADMAP.md"
BREED_INFO_CSV = ROOT / "data" / "breed_info.csv"
BREED_PHOTOS_CSV = ROOT / "data" / "breed_photos.csv"
BREED_FACES_CSV = ROOT / "data" / "breed_faces.csv"
PHOTO_ID_BREEDS_CSV = ROOT / "data" / "photo_id_breeds.csv"
PHOTO_ID_MODEL = ROOT / "models" / "dog_breeds.onnx"

SIGHTING_COLUMNS = ["id", "breed", "seen_on", "location", "dog_name", "notes", "photo_path",
                    "dog_ids"]  # dog_ids: the dog profiles tagged in it


def load_breeds(csv_path: Path = BREEDS_CSV) -> pd.DataFrame:
    """Breeds ordered by popularity rank, with columns: rank, breed.

    The AKC top 100 have a rank. Breeds added after them (the ones Photo ID knows) have none
    (<NA>) and come last, in A-Z order."""
    breeds = pd.read_csv(csv_path, dtype={"rank": "Int64"})
    breeds["breed"] = breeds["breed"].str.strip()
    return breeds.sort_values(["rank", "breed"]).reset_index(drop=True)


@dataclass(frozen=True)
class BreedProfile:
    """What the life list shows when you open a breed: a photo and a short intro."""
    breed: str
    origin: str
    temperament: str
    intro: str
    fun_fact: str
    image_url: str = ""
    credit: str = ""     # photographer, as named on Wikimedia Commons
    licence: str = ""    # e.g. "CC BY-SA 4.0"
    source: str = ""     # the photo's Commons page (credit and licence details)
    # Where the photo sits in a small square or circle picture, so it shows the dog's face
    # (set with scripts/face_cropper.py). CSS background-position (%) and background-size (%).
    face_x: float | None = None
    face_y: float | None = None
    zoom: float | None = None


THUMB_WIDTH = 120  # px: sharp at ~48px on a phone screen, and only ~5 KB each


def thumbnail_url(image_url: str, width: int = THUMB_WIDTH) -> str:
    """A small version of a Wikimedia Commons photo, for thumbnails.

    Commons serves resized copies at .../thumb/<path>/<width>px-<file name>, so
    "/960px-" addresses just change their width, and full-size originals get the thumb
    form. Any other address is returned unchanged.
    """
    sized = re.sub(r"/\d+px-([^/]+)$", rf"/{width}px-\1", image_url)
    if sized != image_url:
        return sized
    original = re.match(r"(https://upload\.wikimedia\.org/wikipedia/commons)/(\w/\w\w)/([^/]+)$",
                        image_url)
    if not original:
        return image_url
    base, folder, name = original.groups()
    thumb_name = f"{name}.png" if name.lower().endswith(".svg") else name  # SVGs come as PNG
    return f"{base}/thumb/{folder}/{name}/{width}px-{thumb_name}"


def load_breed_profiles(info_csv: Path = BREED_INFO_CSV,
                        photos_csv: Path = BREED_PHOTOS_CSV,
                        faces_csv: Path = BREED_FACES_CSV) -> dict[str, BreedProfile]:
    """{breed: BreedProfile}. Text comes from breed_info.csv (written by hand), photos
    from breed_photos.csv (made by scripts/fetch_breed_photos.py) and face crops from
    breed_faces.csv (made by scripts/face_cropper.py). A breed with no photo or crop row
    still gets its text."""
    info = pd.read_csv(info_csv, dtype=str, keep_default_na=False)
    photos = pd.read_csv(photos_csv, dtype=str, keep_default_na=False)
    rows = info.merge(photos, on="breed", how="left").fillna("")
    faces = {}
    if faces_csv.exists():
        faces = {row["breed"]: {k: float(row[k]) for k in ("face_x", "face_y", "zoom")}
                 for row in pd.read_csv(faces_csv, dtype=str).to_dict("records")}
    return {row["breed"]: BreedProfile(**row, **faces.get(row["breed"], {}))
            for row in rows.to_dict("records")}


FACE_PHOTO_WIDTHS = (120, 330, 500, 960)  # px: sizes Wikimedia Commons serves


def face_photo(profile: BreedProfile, box_px: int = 56) -> tuple[str, str] | None:
    """(photo address, CSS) to draw a breed's face-cropped photo as a background in a
    square of up to box_px, or None if it has no photo or crop. Zoomed-in crops get a
    bigger copy of the photo, so the face stays sharp on high-resolution phone screens."""
    if not profile.image_url or profile.zoom is None:
        return None
    needed = profile.zoom / 100 * box_px * 2  # 2 screen pixels per CSS pixel
    width = next((w for w in FACE_PHOTO_WIDTHS if w >= needed), FACE_PHOTO_WIDTHS[-1])
    css = (f"background-size:{profile.zoom:g}%;"
           f"background-position:{profile.face_x:g}% {profile.face_y:g}%")
    return thumbnail_url(profile.image_url, width), css


def sightings_frame(rows: list[dict]) -> pd.DataFrame:
    """Turn sighting rows from any backend into a DataFrame with a fixed set of columns."""
    return pd.DataFrame(rows, columns=SIGHTING_COLUMNS)


# --- Sighting photos ---------------------------------------------------------------

PHOTO_TYPES = ["jpg", "jpeg", "png", "webp"]  # what the photo picker accepts
MAX_PHOTO_UPLOAD_MB = 20  # a phone camera photo is usually 2-8 MB
PHOTO_MAX_SIDE = 1600  # px: plenty for Photo ID, and about 300 KB as a JPEG
PHOTO_QUALITY = 85
NOT_A_PHOTO = "That file doesn't look like a photo. Try a JPG or PNG."


def prepare_photo(data: bytes, max_side: int = PHOTO_MAX_SIDE) -> bytes:
    """Turn an uploaded photo into a small JPEG that's safe to store.

    - Turned the right way up (phones often save photos sideways plus a "rotate me" note).
    - Shrunk so its longest side is at most `max_side` pixels.
    - Saved without its metadata (EXIF), which can include the GPS spot it was taken at.
    Raises ValueError if the file isn't an image.
    """
    from PIL import Image, ImageOps  # Pillow comes with Streamlit

    try:
        with Image.open(io.BytesIO(data)) as img:
            img = ImageOps.exif_transpose(img)
            img.thumbnail((max_side, max_side))
            out = io.BytesIO()
            # A fresh RGB copy carries no EXIF or other metadata into the saved file.
            img.convert("RGB").save(out, format="JPEG", quality=PHOTO_QUALITY, optimize=True)
    except (OSError, SyntaxError, ValueError, Image.DecompressionBombError) as err:
        raise ValueError(NOT_A_PHOTO) from err
    return out.getvalue()


# --- Date and place from a photo's metadata ----------------------------------------
# Phones note when (and often where) a photo was taken in its EXIF metadata. Spotted! reads
# it from the original upload, before prepare_photo strips it, to fill in the date and
# suggest a place name. Only the place name the member keeps is saved, never coordinates.
# Many photos carry none of this (screenshots, some phone browsers remove the location
# when a photo is picked), and then nothing is filled in.

EXIF_IFD, GPS_IFD = 0x8769, 0x8825  # where the camera details and the GPS spot are kept
DATE_TAKEN, DATE_CHANGED = 0x9003, 0x0132  # DateTimeOriginal, DateTime
PLACE_DECIMALS = 3  # about 100 m: the place lookup is never sent a precise spot


@dataclass(frozen=True)
class PhotoDetails:
    taken_on: date | None = None  # the day the photo was taken
    where: tuple[float, float] | None = None  # (latitude, longitude), rounded


def _exif_date(text) -> date | None:
    """EXIF dates look like "2025:06:01 14:30:00" (the camera's local time)."""
    try:
        return datetime.strptime(str(text).strip()[:10], "%Y:%m:%d").date()
    except ValueError:
        return None


def _gps_degrees(value, ref) -> float | None:
    """EXIF GPS is (degrees, minutes, seconds) plus "N"/"S" or "E"/"W"."""
    try:
        d, m, s = (float(part) for part in value)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    degrees = d + m / 60 + s / 3600
    if isinstance(ref, bytes):
        ref = ref.decode(errors="ignore")
    return -degrees if str(ref).strip().upper() in ("S", "W") else degrees


def photo_details(data: bytes) -> PhotoDetails:
    """When and where a photo was taken, from its metadata, as far as it says.

    Never raises: a photo with no (or odd) metadata just gives empty details.
    """
    from PIL import Image  # Pillow comes with Streamlit

    try:
        with Image.open(io.BytesIO(data)) as img:
            exif = img.getexif()
            camera = exif.get_ifd(EXIF_IFD)
            gps = exif.get_ifd(GPS_IFD)
    except Exception:  # not an image, or metadata Pillow can't read
        return PhotoDetails()
    taken_on = _exif_date(camera.get(DATE_TAKEN) or exif.get(DATE_CHANGED) or "")
    lat = _gps_degrees(gps.get(2), gps.get(1, "N"))
    lon = _gps_degrees(gps.get(4), gps.get(3, "E"))
    where = None
    if lat is not None and lon is not None and abs(lat) <= 90 and abs(lon) <= 180 \
            and (lat, lon) != (0, 0):  # 0,0 is what some apps write for "no location"
        where = round(lat, PLACE_DECIMALS), round(lon, PLACE_DECIMALS)
    return PhotoDetails(taken_on, where)


# Address parts from OpenStreetMap's reverse geocoder (Nominatim), most specific first.
PLACE_SPOT_KEYS = ("park", "leisure", "nature_reserve", "tourism", "beach")
PLACE_AREA_KEYS = ("suburb", "neighbourhood", "quarter", "village", "hamlet")
PLACE_TOWN_KEYS = ("city", "town", "village", "municipality", "county")


def place_name(address: dict) -> str | None:
    """A short place name, like "Hyde Park, London" or "Clapham, London", from a
    reverse-geocoded address (Nominatim's `address` dict). None if it has nothing useful."""
    def first(keys):
        return next((str(address[k]).strip() for k in keys if str(address.get(k) or "").strip()),
                    "")

    spot = first(PLACE_SPOT_KEYS) or first(PLACE_AREA_KEYS)
    town = first(PLACE_TOWN_KEYS)
    parts = [p for i, p in enumerate([spot, town]) if p and p not in [spot, town][:i]]
    return ", ".join(parts) or None


def photo_path(user_id: str, photo_id: str) -> str:
    """Where a sighting photo lives in the storage bucket: "<user id>/<photo id>.jpg".

    The storage rules in supabase/schema.sql only let a user touch files in the folder
    named after their own id, so the folder must come first.
    """
    return f"{user_id}/{photo_id}.jpg"


# --- Photo ID: breed suggestions from a photo -------------------------------------------
# A small ready-made image model (models/dog_breeds.onnx, MobileNetV3 trained on ImageNet,
# whose 1,000 things include 118 dog breeds) looks at the photo. data/photo_id_breeds.csv
# lists the model's dog classes and which of our breeds each one is (blank if we don't
# list that breed). cerberus/photo_id.py runs the model; these functions do the rest.
# The model only suggests: the member always picks the breed.

PHOTO_ID_SIZE = 224  # px: the model looks at a 224 x 224 square
LIKELY = 0.7  # a guess this sure is "Very likely"
POSSIBLE = 0.3  # ... this sure "Possible", below it "Long shot". A best guess below
# POSSIBLE means "not sure": no suggestions, pick the breed yourself.
MIN_DOG = 0.5  # how sure the model must be that there's a dog at all
MIN_SHOWN = 0.05  # guesses below this aren't worth showing


@dataclass(frozen=True)
class BreedGuess:
    breed: str
    score: float  # 0 to 1: how much of the model's "it's a dog" belief went to this breed
    label: str  # "Very likely", "Possible" or "Long shot"


@dataclass(frozen=True)
class PhotoGuesses:
    is_dog: bool  # False: the model can't see a dog in the photo
    guesses: tuple[BreedGuess, ...]  # best first; empty if no dog or not sure


def load_photo_id_breeds(text: str) -> dict[int, str]:
    """Parse data/photo_id_breeds.csv: model class number -> our breed name, or "" for a
    dog breed the model knows that isn't on our list (it still counts as "a dog")."""
    frame = pd.read_csv(io.StringIO(text), dtype={"breed": str}, keep_default_na=False)
    return {int(row.class_id): row.breed.strip() for row in frame.itertuples()}


def confidence_label(score: float) -> str:
    return "Very likely" if score >= LIKELY else "Possible" if score >= POSSIBLE else "Long shot"


def breed_guesses(probs, class_breeds: dict[int, str], top: int = 3) -> PhotoGuesses:
    """Turn the model's scores for each class (probabilities adding up to 1) into our top
    breed guesses. Classes for the same breed add up (toy, miniature and standard
    poodle are all Poodle). Scores are shares of the dog classes only, so a clear photo
    of a Beagle scores near 1 for Beagle however much else is in the picture."""
    dog = float(sum(probs[i] for i in class_breeds))
    if dog < MIN_DOG:
        return PhotoGuesses(False, ())
    scores: dict[str, float] = {}
    for i, breed in class_breeds.items():
        if breed:
            scores[breed] = scores.get(breed, 0.0) + float(probs[i]) / dog
    best = sorted(scores, key=scores.get, reverse=True)[:top]
    if not best or scores[best[0]] < POSSIBLE:
        return PhotoGuesses(True, ())
    return PhotoGuesses(True, tuple(BreedGuess(b, scores[b], confidence_label(scores[b]))
                                    for b in best if scores[b] >= MIN_SHOWN))


def photo_id_pixels(data: bytes, size: int = PHOTO_ID_SIZE):
    """The photo as the model wants it: the middle square, shrunk to size x size, as a
    1 x size x size x 3 array of red/green/blue values from 0 to 255.
    Raises ValueError if the file isn't an image."""
    import numpy as np
    from PIL import Image, ImageOps

    try:
        with Image.open(io.BytesIO(data)) as img:
            img = ImageOps.exif_transpose(img).convert("RGB")
            side = min(img.size)
            left, top = (img.width - side) // 2, (img.height - side) // 2
            img = img.crop((left, top, left + side, top + side)).resize(
                (size, size), Image.Resampling.BILINEAR)
            return np.asarray(img, dtype=np.float32)[None]
    except (OSError, SyntaxError, ValueError, Image.DecompressionBombError) as err:
        raise ValueError(NOT_A_PHOTO) from err


# --- Verified and unverified breeds ----------------------------------------------------
# Every breed in data/breeds.csv is verified: it's on the life list and counts towards
# lifers and badges. Members can also type in a breed that isn't listed. That's an
# unverified breed: it's logged, shown with an "Unverified breed" badge and added to the
# shared list of member-added breeds (the user_breeds table) for the owner to review.
# Once a breed is added to data/breeds.csv it's verified, and old sightings of it count.

MAX_BREED_LENGTH = 100  # matches the check on sightings.breed in supabase/schema.sql
UNVERIFIED = "Unverified breed"


def clean_breed(text: str | None, known: Iterable[str] = ()) -> str:
    """Tidy a breed picked or typed on the Spotted! form. A known breed (verified, or
    already added by a member) typed in any capitals becomes its usual spelling; anything
    else is kept as typed, with spaces tidied. A cross typed as "beagle x pug" is tidied
    the same way, part by part ("Beagle x Pug"). Raises ValueError if empty or too long."""
    text = " ".join((text or "").split())
    if not text:
        raise ValueError("Pick a breed first, or type one in.")
    if len(text) > MAX_BREED_LENGTH:
        raise ValueError(f"Please keep the breed under {MAX_BREED_LENGTH} characters.")
    known = list(known)
    parts = _CROSS_SPLIT.split(text)
    if len(parts) == 2 and all(parts):
        return cross_name(*parts, known=known)
    spelling = {name.lower(): name for name in known}
    return spelling.get(text.lower(), text)


# --- Cross breeds ----------------------------------------------------------------------
# A cross (a dog whose parents are two different breeds) is logged with its breed written
# as "Breed A x Breed B", so it reads the same everywhere (Social, Profile) with no extra
# database column. The first sighting of each cross is a lifer, but crosses don't count
# towards badges or the "of 141 breeds" total (those are for verified breeds). They get
# their own "Crosses" list on the life list.

CROSS = "Cross breed"
# The owner's choice (27 Nov 2026), kept as one switch so it's easy to change back:
# True = the first sighting of each cross is a lifer. Lifers are worked out from
# sightings every time (nothing is stored), so flipping this updates everyone's history.
CROSSES_ARE_LIFERS = True
CROSS_SEPARATOR = " x "
_CROSS_SPLIT = re.compile(r"\s+[xX×]\s+")


def cross_name(first: str | None, second: str | None, known: Iterable[str] = ()) -> str:
    """The breed to log for a cross of two breeds: "Labrador Retriever x Poodle". Each
    parent is tidied like clean_breed (a known breed gets its usual spelling), and they're
    put in A to Z order, so a Poodle x Labrador is the same cross as a Labrador x Poodle
    (and only one of them is a lifer). Raises
    ValueError if a parent is missing, both are the same, or the name gets too long."""
    if not (first or "").strip() or not (second or "").strip():
        raise ValueError("Pick both breeds in the cross.")
    known = list(known)
    first, second = clean_breed(first, known), clean_breed(second, known)
    if is_cross(first) or is_cross(second):
        raise ValueError("Pick one breed in each box.")
    if first.lower() == second.lower():
        raise ValueError("Pick two different breeds for a cross.")
    first, second = sorted((first, second), key=str.lower)  # same cross, same name
    name = f"{first}{CROSS_SEPARATOR}{second}"
    if len(name) > MAX_BREED_LENGTH:
        raise ValueError(f"Please keep the two breeds under {MAX_BREED_LENGTH} characters "
                         "together.")
    return name


def cross_parents(breed: str | None) -> tuple[str, str] | None:
    """The two parent breeds of a cross ("Beagle x Pug" gives ("Beagle", "Pug")), or None
    if the breed isn't a cross."""
    parts = (breed or "").split(CROSS_SEPARATOR)
    if len(parts) == 2 and all(p.strip() for p in parts):
        return parts[0], parts[1]
    return None


def is_cross(breed: str | None) -> bool:
    """True for a cross breed logged as "Breed A x Breed B"."""
    return cross_parents(breed) is not None


# --- Lifer celebration --------------------------------------------------------------

FACE_BALLOONS = 12  # how many breed faces float up for a new lifer


def celebration_layout(breed: str, count: int = FACE_BALLOONS) -> list[dict]:
    """Where each floating face goes when a lifer is logged: one dict per face, with the
    breed whose face it shows (a cross takes turns between its two parents), how far
    across the screen it starts (left, %), when it sets off and how long it takes to
    rise (delay, seconds), and its size (rem). Spread out but fixed, so tests can check
    it and the faces never bunch up on one side."""
    parents = cross_parents(breed)
    faces = list(parents) if parents else [breed]
    layout = []
    for i in range(count):
        layout.append({
            "breed": faces[i % len(faces)],
            "left": round(4 + (i * 5 % count) / count * 80, 1),  # 4-84% across, shuffled
            "delay": round(i * 0.35, 2),
            "rise": round(8 + (i * 5 % 4) * 0.75, 2),  # 8-10.25 s, slower than balloons
            "size": (4.25, 3.5, 5.0)[i % 3],
        })
    return layout


_MARKDOWN_SPECIAL = re.compile(r"([\\`*_{}\[\]()#+\-.!|<>~:$])")


def escape_markdown(text: str | None) -> str:
    """Text members typed, made safe to put inside st.markdown: every character Markdown
    (or Streamlit's extras, like :red[...] and $maths$) could act on gets a backslash.
    A missing value (None, or pandas' NaN for an empty optional field) gives ""."""
    if text is None or (isinstance(text, float) and text != text):  # NaN != NaN
        return ""
    return _MARKDOWN_SPECIAL.sub(r"\\\1", str(text))


def _breed_counts(rest: pd.DataFrame) -> pd.DataFrame:
    """breed, first_seen, times_seen for these sightings, most seen first."""
    return (rest.groupby("breed")
            .agg(first_seen=("seen_on", "min"), times_seen=("seen_on", "size"))
            .reset_index()
            .sort_values(["times_seen", "breed"], ascending=[False, True])
            .reset_index(drop=True))


def unverified_breeds(sightings: pd.DataFrame, listed: set[str]) -> pd.DataFrame:
    """Your sightings of breeds that aren't verified yet (crosses have their own list):
    breed, first_seen, times_seen, most seen first."""
    crosses = sightings["breed"].map(is_cross).astype(bool)
    return _breed_counts(sightings[~sightings["breed"].isin(listed) & ~crosses])


def cross_breeds(sightings: pd.DataFrame) -> pd.DataFrame:
    """Your sightings of cross breeds ("Labrador Retriever x Poodle"): breed, first_seen,
    times_seen, most seen first."""
    return _breed_counts(sightings[sightings["breed"].map(is_cross).astype(bool)])


def is_lifer(sightings: pd.DataFrame, breed: str, listed: set[str] | None = None) -> bool:
    """True if this breed isn't in the spotter's sightings yet. If `listed` is given, only
    those (verified) breeds, and crosses if CROSSES_ARE_LIFERS, can be lifers."""
    if listed is not None and breed not in listed:
        if not (CROSSES_ARE_LIFERS and is_cross(breed)):
            return False
    return breed not in set(sightings["breed"])


def life_list(breeds: pd.DataFrame, sightings: pd.DataFrame) -> pd.DataFrame:
    """Every breed with first-seen date and number of sightings (0 if not seen yet)."""
    stats = (
        sightings.groupby("breed")
        .agg(first_seen=("seen_on", "min"), times_seen=("seen_on", "size"))
        .reset_index()
    )
    out = breeds.merge(stats, on="breed", how="left")
    out["times_seen"] = out["times_seen"].fillna(0).astype(int)
    return out.sort_values(["rank", "breed"]).reset_index(drop=True)


LIFE_LIST_FILTERS = ["All", "Collected", "Still to find"]


def filter_life_list(life: pd.DataFrame, show: str = "All", query: str = "") -> pd.DataFrame:
    """Narrow a life list to collected / still-to-find breeds and a case-insensitive search."""
    out = life
    if show == "Collected":
        out = out[out["times_seen"] > 0]
    elif show == "Still to find":
        out = out[out["times_seen"] == 0]
    query = (query or "").strip()
    if query:
        out = out[out["breed"].str.contains(query, case=False, regex=False)]
    return out


def recent_first(sightings: pd.DataFrame) -> pd.DataFrame:
    """Sightings newest first (by date seen, then by when they were logged)."""
    return sightings.sort_values(["seen_on", "id"], ascending=False)


# --- What's new: releases from CHANGELOG.md, upcoming features from ROADMAP.md ----------

@dataclass(frozen=True)
class Release:
    version: str        # "0.6.0"
    date: str           # ISO "YYYY-MM-DD"
    title: str
    changes: tuple[str, ...]


RELEASE_HEADING = re.compile(r"^## (\d+\.\d+\.\d+) - (\d{4}-\d{2}-\d{2})(?: - (.+))?$")


def parse_changelog(text: str) -> list[Release]:
    """Releases in the order the changelog lists them (newest first).

    Each release is a `## <version> - <date> - <title>` heading followed by `- ` bullets.
    Anything else (the intro, other headings) is ignored.
    """
    releases: list[Release] = []
    current: dict | None = None
    for line in text.splitlines():
        line = line.rstrip()
        if line.startswith("## "):
            if current:
                releases.append(Release(**current))
            match = RELEASE_HEADING.match(line)
            current = None
            if match:
                version, date, title = match.groups()
                current = {"version": version, "date": date, "title": title or "",
                           "changes": ()}
        elif current and line.startswith("- "):
            current["changes"] += (line[2:].strip(),)
    if current:
        releases.append(Release(**current))
    return releases


@dataclass(frozen=True)
class RoadmapItem:
    key: str            # stable id for +1 votes, e.g. "photo-upload"
    title: str          # "Photo upload"
    text: str           # the full line as Markdown, e.g. "**Photo upload** with a sighting"


def _section(text: str, name: str) -> list[str]:
    """The lines under a `## <name>` heading, up to the next `## ` heading."""
    lines, inside = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            inside = line[3:].strip() == name
        elif inside:
            lines.append(line)
    return lines


def _plain(markdown: str) -> str:
    """Drop links (keep their text) and code backticks, which mean nothing to users."""
    markdown = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", markdown)
    return markdown.replace("`", "").strip()


def feature_key(title: str) -> str:
    """A short, stable id for a feature: "Guided manual ID" -> "guided-manual-id"."""
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:100]


def upcoming_features(roadmap: str, sections: tuple[str, ...] = ("Now", "Next")) -> list[RoadmapItem]:
    """Unticked top-level `- [ ]` items from the roadmap's Now and Next sections.

    The indented notes under each item are for developers, so they're left out.
    """
    items = []
    for name in sections:
        for line in _section(roadmap, name):
            if not line.startswith("- [ ] "):
                continue
            text = _plain(line[len("- [ ] "):])
            bold = re.match(r"\*\*(.+?)\*\*", text)
            title = bold.group(1) if bold else text
            items.append(RoadmapItem(key=feature_key(title), title=title, text=text))
    return items


def has_unseen_update(latest: str | None, seen: str | None) -> bool:
    """True if `latest` (e.g. "0.7.0") is newer than the version the user last saw.

    Someone who has never opened Settings (seen is None) hasn't seen any update yet.
    """
    if not latest:
        return False
    try:
        return seen is None or _version(seen) < _version(latest)
    except ValueError:  # a garbled saved version: treat it as unseen
        return True


def _version(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in text.split("."))


MAX_SUGGESTION_LENGTH = 500


def clean_suggestion(text: str) -> str:
    """Trim a feature suggestion and check its length. Raises ValueError if it can't be sent."""
    text = (text or "").strip()
    if not text:
        raise ValueError("Write your idea first.")
    if len(text) > MAX_SUGGESTION_LENGTH:
        raise ValueError(f"Please keep it under {MAX_SUGGESTION_LENGTH} characters.")
    return text


# --- Profiles and the Social feed ------------------------------------------------------

MIN_USERNAME_LENGTH, MAX_USERNAME_LENGTH = 3, 30
# A profile picture ("avatar") is a breed name, shown as that breed's photo. New members
# start with the 🐶 emoji, and the older emoji choices below still work for anyone who
# picked one before breed photos were offered.
AVATARS = ["🐶", "🐕", "🐩", "🦮", "🐕‍🦺", "🐾", "🦴", "🎾", "🐺", "🦊"]
MIXED_BREED = "Mixed breed / other"
MAX_DOGS = 5
MAX_DOG_NAME_LENGTH = 40
USERNAME_TAKEN = "That username is taken. Please choose another."


def new_profile(username: str) -> dict:
    """A brand-new member's profile: sharing is on by default."""
    return {"username": username, "avatar": AVATARS[0], "favourite_breed": None,
            "dogs": [], "share_sightings": True}


def clean_profile(profile: dict, breed_names: set[str] | None = None) -> dict:
    """Check and tidy a profile before saving it. Raises ValueError with a friendly message.

    `breed_names` are the breeds whose photo can be a profile picture (read from
    breeds.csv if not given).
    """
    username = (profile.get("username") or "").strip()
    if not MIN_USERNAME_LENGTH <= len(username) <= MAX_USERNAME_LENGTH:
        raise ValueError(f"Username must be {MIN_USERNAME_LENGTH} to {MAX_USERNAME_LENGTH} characters.")
    avatar = profile.get("avatar")
    if breed_names is None:
        breed_names = set(load_breeds()["breed"])
    if avatar not in AVATARS and avatar not in breed_names:
        raise ValueError("Pick a profile picture from the list.")
    dogs = []
    for dog in profile.get("dogs") or []:
        name = (dog.get("name") or "").strip()
        breed = dog.get("breed") or None
        if not name and not breed:
            continue  # an empty row: ignore it
        if not name:
            raise ValueError("Give each of your dogs a name.")
        if len(name) > MAX_DOG_NAME_LENGTH:
            raise ValueError(f"Dog names can be up to {MAX_DOG_NAME_LENGTH} characters.")
        dogs.append({"name": name, "breed": breed})
    if len(dogs) > MAX_DOGS:
        raise ValueError(f"You can list up to {MAX_DOGS} dogs.")
    return {"username": username, "avatar": avatar,
            "favourite_breed": profile.get("favourite_breed") or None,
            "dogs": dogs, "share_sightings": bool(profile.get("share_sightings", True))}


def username_candidates(base: str, tries: int = 50):
    """Names to try for a new profile when usernames must be unique: "pat", "pat2", "pat3", ..."""
    base = (base or "").strip()[:MAX_USERNAME_LENGTH - 2]
    base = base.ljust(MIN_USERNAME_LENGTH, "_")  # very short names get padded: "al" -> "al_"
    yield base
    for n in range(2, tries + 1):
        yield f"{base}{n}"


def social_feed(sightings: list[dict], profiles: dict[str, dict],
                milestones: dict[int, str] | None = None) -> list[dict]:
    """Sightings for the Social tab, each with its spotter's username and avatar, and
    "badge": the key of the milestone badge that sighting earned, or None.

    `profiles` maps user id -> profile; `milestones` maps sighting id -> badge key (from
    `milestone_sightings`). Sightings from members without a profile, or who have switched
    sharing off, are left out. Order is kept (newest post first from the backend).
    """
    milestones = milestones or {}
    feed = []
    for s in sightings:
        who = profiles.get(s["user_id"])
        if who and who.get("share_sightings", True):
            feed.append({**s, "username": who["username"], "avatar": who["avatar"],
                         "badge": milestones.get(s["id"])})
    return feed

def posted_on(created_at: str | None, tz: str | None = None) -> date | None:
    """The day a sighting was posted, from its `created_at` timestamp, in time zone `tz`
    (the member's browser zone, like "Europe/London"; UTC if missing or unknown). None if
    there's no timestamp. Can differ from the date seen, which a photo may set earlier."""
    if not created_at:
        return None
    try:
        when = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo is not None and tz:
        try:
            from zoneinfo import ZoneInfo
            when = when.astimezone(ZoneInfo(tz))
        except Exception:  # unknown zone, or no time zone data on this machine
            pass
    return when.date()


# --- Dog profiles: members' own dogs, taggable in posts by @username ------------------

DOG_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.]{3,30}$")  # matches the check in schema.sql
MAX_DOG_BIO_LENGTH = 300
DOG_PHOTO_MAX_SIDE = 800  # px: a profile picture needs less than a sighting photo
DOG_USERNAME_TAKEN = "That dog username is taken. Please choose another."
BAD_DOG_USERNAME = ("Dog usernames are 3 to 30 letters, numbers, dots or underscores "
                    "(no spaces), like rex_the_lab.")


def clean_dog(dog: dict, breed_names: set[str] | None = None) -> dict:
    """Check and tidy a dog profile before saving it. Raises ValueError with a friendly
    message. `breed_names` are the allowed breeds (read from breeds.csv if not given);
    "Mixed breed / other" is always allowed, and so is leaving the breed empty."""
    username = (dog.get("username") or "").strip().lstrip("@")
    if not DOG_USERNAME_RE.match(username):
        raise ValueError(BAD_DOG_USERNAME)
    name = (dog.get("name") or "").strip()
    if not name:
        raise ValueError("Give your dog a name.")
    if len(name) > MAX_DOG_NAME_LENGTH:
        raise ValueError(f"Dog names can be up to {MAX_DOG_NAME_LENGTH} characters.")
    breed = dog.get("breed") or None
    if breed_names is None:
        breed_names = set(load_breeds()["breed"])
    if breed is not None and breed not in breed_names and breed != MIXED_BREED:
        raise ValueError("Pick your dog's breed from the list.")
    bio = (dog.get("bio") or "").strip() or None
    if bio and len(bio) > MAX_DOG_BIO_LENGTH:
        raise ValueError(f"Keep the bio under {MAX_DOG_BIO_LENGTH} characters.")
    return {"username": username, "name": name, "breed": breed, "bio": bio,
            "photo_path": dog.get("photo_path") or None}


def dog_username_candidates(name: str, tries: int = 50):
    """Usernames to try for a dog called `name`: "rex", "rex2", ... (letters, numbers,
    dots and underscores only, so "Mr Biscuit" -> "mr_biscuit")."""
    base = re.sub(r"[^a-z0-9_.]", "", re.sub(r"\s+", "_", (name or "").strip().lower()))
    base = (base or "dog")[:27].ljust(3, "_")
    yield base
    for n in range(2, tries + 1):
        yield f"{base}{n}"


def dog_photo_path(user_id: str, photo_id: str) -> str:
    """Where a dog's profile photo lives: in its owner's folder, like sighting photos."""
    return f"{user_id}/dogs/{photo_id}.jpg"


def dog_label(dog: dict) -> str:
    """How a dog appears in pickers: "@rex · Rex (Labrador Retriever)"."""
    breed = f" ({dog['breed']})" if dog.get("breed") else ""
    return f"@{dog['username']} · {dog['name']}{breed}"


def tagged_names(dogs: list[dict]) -> str:
    """The "dog's name" to log when the spotter tagged dogs but left the name empty:
    "Rex", or "Rex and Bella", or "Rex, Bella and Max"."""
    names = [d["name"] for d in dogs]
    return " and ".join([", ".join(names[:-1]), names[-1]]) if len(names) > 1 else "".join(names)


def tagged_breed(dogs: list[dict]) -> str | None:
    """The breed to log when the spotter tagged dogs but didn't pick a breed: the tagged
    dogs' breed if they all share one known breed (not "Mixed breed / other"), else None."""
    known = {d.get("breed") for d in dogs}
    if len(known) == 1:
        (breed,) = known
        if breed and breed != MIXED_BREED:
            return breed
    return None


# --- Badges: milestones earned from how many breeds you've spotted ------------------------

@dataclass(frozen=True)
class Badge:
    key: str            # stable id, e.g. "breeds-10"
    icon: str           # a hand-drawn icon's name in cerberus/sketches.py SKETCHES
    name: str           # "Pack of 10"
    goal: int           # how many different breeds earn it

    @property
    def description(self) -> str:
        return "Spot your first breed" if self.goal == 1 else f"Spot {self.goal} different breeds"


# A badge for your first breed, one every 5 breeds up to 100, then every 10, and a last one
# for every verified breed (141; a test checks it matches data/breeds.csv). Keys are stable ids
# ("breeds-<goal>"), so names and icons can change without anyone losing a badge.
BADGES = (
    Badge("first-lifer", "paw", "First lifer", 1),
    Badge("breeds-5", "dog", "Puppy steps", 5),
    Badge("breeds-10", "bone", "Pack of 10", 10),
    Badge("breeds-15", "lead", "Walkies regular", 15),
    Badge("breeds-20", "frisbee", "Frisbee fetcher", 20),
    Badge("breeds-25", "ball", "Quarter century", 25),
    Badge("breeds-30", "sun", "Dog days", 30),
    Badge("breeds-35", "nose", "Super sniffer", 35),
    Badge("breeds-40", "tracks", "Trail tracker", 40),
    Badge("breeds-45", "zoom", "Zoomies", 45),
    Badge("breeds-50", "medal", "Halfway hound", 50),
    Badge("breeds-55", "rosette", "Prize poodle", 55),
    Badge("breeds-60", "moon", "Howl of fame", 60),
    Badge("breeds-65", "compass", "Pathfinder", 65),
    Badge("breeds-70", "kennel", "Kennel club", 70),
    Badge("breeds-75", "tail", "Three-quarter tail", 75),
    Badge("breeds-80", "star", "Star spotter", 80),
    Badge("breeds-85", "target", "Sharp eye", 85),
    Badge("breeds-90", "dogstar", "Dog star", 90),
    Badge("breeds-95", "first", "Best in show", 95),
    Badge("breeds-100", "trophy", "Top dog", 100),
    Badge("breeds-110", "suitcase", "Globetrotter", 110),
    Badge("breeds-120", "map", "World tour", 120),
    Badge("breeds-130", "telescope", "Rare-breed hunter", 130),
    Badge("breeds-140", "gem", "Hidden gem", 140),
    Badge("breeds-141", "crown", "Leader of the pack", 141),
)


@dataclass(frozen=True)
class BadgeProgress:
    badge: Badge
    earned_on: str | None   # ISO date the milestone breed was first seen, or None
    have: int               # breeds spotted so far (capped at the goal)

    @property
    def earned(self) -> bool:
        return self.earned_on is not None

    @property
    def to_go(self) -> int:
        return self.badge.goal - self.have


def badge_progress(sightings: pd.DataFrame, badges: tuple[Badge, ...] = BADGES,
                   listed: set[str] | None = None) -> list[BadgeProgress]:
    """Every badge with whether it's earned, and when.

    A badge for N breeds is earned on the day the Nth different breed was first seen.
    It's worked out from your sightings each time (no table to keep in step), so dates are
    right even for sightings logged out of order, and deleting a sighting can undo a badge.
    If `listed` is given, only those (verified) breeds count.
    """
    if listed is not None:
        sightings = sightings[sightings["breed"].isin(listed)]
    first_seen = sorted(sightings.groupby("breed")["seen_on"].min().astype(str))
    count = len(first_seen)
    return [BadgeProgress(badge, first_seen[badge.goal - 1] if count >= badge.goal else None,
                          min(count, badge.goal))
            for badge in badges]


def badge_for_count(count: int, badges: tuple[Badge, ...] = BADGES) -> Badge | None:
    """The badge earned by reaching exactly `count` breeds (to celebrate a new lifer)."""
    return next((b for b in badges if b.goal == count), None)


BADGES_BY_KEY = {b.key: b for b in BADGES}


def milestone_sightings(sightings: Iterable[dict], listed: set[str],
                        badges: tuple[Badge, ...] = BADGES) -> dict[int, str]:
    """{sighting id: badge key} for each sighting that earned its spotter a badge.

    Works per member, by the same rule as `badge_progress`: a member's badge for N breeds
    goes with the first sighting of their Nth different verified breed (in date order, then
    the order they were logged). Sightings need id, user_id, breed and seen_on.
    """
    firsts: dict[str, dict[str, tuple]] = {}  # user id -> breed -> (seen_on, id)
    for s in sightings:
        if s["breed"] not in listed:
            continue
        key = (str(s["seen_on"]), s["id"])
        mine = firsts.setdefault(s["user_id"], {})
        if s["breed"] not in mine or key < mine[s["breed"]]:
            mine[s["breed"]] = key
    out = {}
    for mine in firsts.values():
        order = sorted(mine.values())
        for badge in badges:
            if len(order) >= badge.goal:
                out[order[badge.goal - 1][1]] = badge.key
    return out


def next_badge(progress: list[BadgeProgress]) -> BadgeProgress | None:
    """The first badge not yet earned, or None once they're all earned."""
    return next((p for p in progress if not p.earned), None)

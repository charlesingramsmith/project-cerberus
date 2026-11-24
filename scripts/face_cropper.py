"""A small local tool for choosing where each breed photo's profile-picture circle sits.

Run it, then open http://localhost:8503 in a browser:

    .venv/Scripts/python.exe scripts/face_cropper.py

Drag a photo inside the circle to move it, and scroll or use the slider to zoom. Every change
is saved straight away to data/breed_faces.csv. The app never runs this; it only reads the CSV.

A crop is stored the way CSS draws it on a square picture, so the app can show it exactly:
  face_x, face_y  background-position in % (0 = left/top edge of the photo, 100 = right/bottom)
  zoom            background-size in % (the photo's width as a % of the circle's width)
"""
from __future__ import annotations

import csv
import io
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from cerberus.logic import BREED_PHOTOS_CSV, load_breeds, thumbnail_url  # noqa: E402

FACES_CSV = ROOT / "data" / "breed_faces.csv"
PAGE = Path(__file__).with_name("face_cropper.html")
FIELDS = ["breed", "face_x", "face_y", "zoom"]
PORT = 8503
EDITOR_WIDTH = 500  # px: a photo size Wikimedia serves that stays sharp when zoomed in


def parse_crops(text: str) -> dict[str, dict]:
    """Read breed_faces.csv text into {breed: {"face_x", "face_y", "zoom"}} (numbers)."""
    crops = {}
    for row in csv.DictReader(io.StringIO(text)):
        crops[row["breed"]] = {k: float(row[k]) for k in FIELDS[1:]}
    return crops


def crops_csv(crops: dict[str, dict], breed_order: list[str]) -> str:
    """Write crops as CSV text in breed rank order, leaving out unknown breeds."""
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    for breed in breed_order:
        if breed in crops:
            crop = crops[breed]
            writer.writerow({"breed": breed, **{k: round(float(crop[k]), 1) for k in FIELDS[1:]}})
    return out.getvalue()


def breed_list() -> list[dict]:
    """Every breed in rank order, with its photo address and any saved crop."""
    with open(BREED_PHOTOS_CSV, encoding="utf-8") as f:
        photos = {row["breed"]: row for row in csv.DictReader(f)}
    saved = parse_crops(FACES_CSV.read_text(encoding="utf-8")) if FACES_CSV.exists() else {}
    return [{"breed": breed,
             "image": thumbnail_url(photos[breed]["image_url"], EDITOR_WIDTH) if breed in photos else "",
             "crop": saved.get(breed)}
            for breed in load_breeds()["breed"]]


class Handler(BaseHTTPRequestHandler):
    def _send(self, body: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/":
            self._send(PAGE.read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/breeds":
            self._send(json.dumps(breed_list()).encode(), "application/json")
        else:
            self._send(b"Not found", "text/plain", 404)

    def do_POST(self) -> None:
        if self.path != "/save":
            return self._send(b"Not found", "text/plain", 404)
        crops = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        order = list(load_breeds()["breed"])
        FACES_CSV.write_text(crops_csv(crops, order), encoding="utf-8")
        self._send(b"{}", "application/json")

    def log_message(self, *args) -> None:  # keep the terminal quiet
        pass


if __name__ == "__main__":
    print(f"Face cropper running at http://localhost:{PORT} (Ctrl+C to stop)")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()

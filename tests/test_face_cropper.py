"""Tests for the face cropper's CSV reading and writing (scripts/face_cropper.py)."""
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "face_cropper.py"
spec = importlib.util.spec_from_file_location("face_cropper", SCRIPT)
face_cropper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(face_cropper)


def test_crops_round_trip_in_breed_order():
    crops = {"Pug": {"face_x": 22, "face_y": 20.04, "zoom": 200},
             "Beagle": {"face_x": 30.55, "face_y": 35, "zoom": 230}}
    text = face_cropper.crops_csv(crops, ["Beagle", "Pug"])
    assert text.splitlines() == ["breed,face_x,face_y,zoom", "Beagle,30.6,35.0,230.0", "Pug,22.0,20.0,200.0"]
    assert face_cropper.parse_crops(text) == {"Beagle": {"face_x": 30.6, "face_y": 35.0, "zoom": 230.0},
                                              "Pug": {"face_x": 22.0, "face_y": 20.0, "zoom": 200.0}}


def test_unknown_breeds_are_left_out():
    text = face_cropper.crops_csv({"Not A Breed": {"face_x": 1, "face_y": 2, "zoom": 3}}, ["Pug"])
    assert text == "breed,face_x,face_y,zoom\n"


def test_every_breed_is_listed_with_a_photo():
    breeds = face_cropper.breed_list()
    assert len(breeds) == 100
    assert all(b["image"].startswith("https://") for b in breeds)

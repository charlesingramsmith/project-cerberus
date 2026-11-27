"""Photo ID: breed suggestions from a photo (logic.breed_guesses and cerberus.photo_id)."""
import io

import numpy as np
import pytest
from PIL import Image

from cerberus import logic
from cerberus.photo_id import PhotoID

CLASSES = {10: "Beagle", 11: "Poodle", 12: "Poodle", 13: "Pug", 14: ""}  # 14: a breed we don't list


def probs(**by_class) -> np.ndarray:
    """1,000 class scores: the given ones, the rest of the total spread over class 0."""
    p = np.zeros(1000)
    for name, value in by_class.items():
        p[int(name[1:])] = value
    p[0] = 1 - p.sum()
    return p


def image_bytes(width=300, height=200, colour=(200, 150, 100)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (width, height), colour).save(out, format="PNG")
    return out.getvalue()


def test_a_clear_photo_gives_a_very_likely_breed():
    result = logic.breed_guesses(probs(c10=0.9, c13=0.08), CLASSES)
    assert result.is_dog
    assert [(g.breed, g.label) for g in result.guesses] == [
        ("Beagle", "Very likely"), ("Pug", "Long shot")]


def test_scores_are_shares_of_the_dog_classes_and_breeds_add_up():
    # Poodle's two classes add up; scores ignore the 40% the model gave to non-dog things.
    result = logic.breed_guesses(probs(c11=0.2, c12=0.2, c10=0.2), CLASSES)
    assert [g.breed for g in result.guesses] == ["Poodle", "Beagle"]
    assert result.guesses[0].score == pytest.approx(2 / 3)
    assert result.guesses[0].label == "Possible"


def test_at_most_three_guesses_and_tiny_ones_are_left_out():
    many = {i: f"Breed {i}" for i in range(10, 20)}
    result = logic.breed_guesses(probs(c10=0.5, c11=0.2, c12=0.2, c13=0.06, c14=0.04), many)
    assert [g.breed for g in result.guesses] == ["Breed 10", "Breed 11", "Breed 12"]
    result = logic.breed_guesses(probs(c10=0.9, c11=0.02), many)
    assert [g.breed for g in result.guesses] == ["Breed 10"]


def test_no_dog_in_the_photo_means_no_guesses():
    result = logic.breed_guesses(probs(c10=0.3), CLASSES)
    assert not result.is_dog and result.guesses == ()


def test_a_weak_best_guess_means_not_sure():
    # Mostly a breed we don't list (class 14): it's a dog, but no confident suggestion.
    result = logic.breed_guesses(probs(c14=0.7, c10=0.1), CLASSES)
    assert result.is_dog and result.guesses == ()


@pytest.mark.parametrize("score, label", [
    (0.95, "Very likely"), (0.7, "Very likely"), (0.5, "Possible"), (0.3, "Possible"),
    (0.1, "Long shot")])
def test_confidence_labels(score, label):
    assert logic.confidence_label(score) == label


def test_the_breed_list_maps_the_models_dog_classes_to_our_breed_names():
    class_breeds = logic.load_photo_id_breeds(
        logic.PHOTO_ID_BREEDS_CSV.read_text(encoding="utf-8"))
    assert list(class_breeds) == list(range(151, 269))  # the model's 118 dog breeds
    named = {b for b in class_breeds.values() if b}
    assert named <= set(logic.load_breeds()["breed"])  # same spelling as breeds.csv
    assert len(named) == 73
    assert [i for i, b in class_breeds.items() if b == "Poodle"] == [265, 266, 267]


def test_photos_become_a_square_for_the_model():
    pixels = logic.photo_id_pixels(image_bytes(300, 200))
    assert pixels.shape == (1, 224, 224, 3) and pixels.dtype == np.float32
    assert pixels[0, 0, 0].tolist() == [200, 150, 100]


def test_photo_id_refuses_files_that_are_not_photos():
    with pytest.raises(ValueError):
        logic.photo_id_pixels(b"not a photo")


@pytest.fixture(scope="module")
def model():
    return PhotoID()


def test_the_model_gives_a_score_for_each_of_its_classes(model):
    p = model.probabilities(image_bytes())
    assert p.shape == (1000,)
    assert p.sum() == pytest.approx(1, abs=1e-3)


def test_a_plain_colour_is_not_a_dog(model):
    result = model.guesses(image_bytes(colour=(30, 120, 220)))
    assert not result.is_dog and result.guesses == ()

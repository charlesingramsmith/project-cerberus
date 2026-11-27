"""Photo ID: run the dog breed model on a photo (see the Photo ID section in logic.py).

The model is a small ready-made image classifier (MobileNetV3, trained on ImageNet) saved
as models/dog_breeds.onnx and run with ONNX Runtime, so the app needs no deep-learning
framework. It runs on the app's own server: photos never go to another company.
"""
from __future__ import annotations

from pathlib import Path

from cerberus import logic


class PhotoID:
    """The loaded model plus the list of which classes are which of our breeds.

    It holds no member data, so one copy can be shared by everyone (st.cache_resource).
    """

    def __init__(self, model_path: Path = logic.PHOTO_ID_MODEL,
                 breeds_csv: Path = logic.PHOTO_ID_BREEDS_CSV):
        import onnxruntime as ort

        options = ort.SessionOptions()
        options.intra_op_num_threads = 1  # small model; be gentle on the shared server
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(model_path), options,
                                            providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        self.class_breeds = logic.load_photo_id_breeds(breeds_csv.read_text(encoding="utf-8"))

    def probabilities(self, photo: bytes):
        """The model's score for each of its 1,000 classes (they add up to 1).
        Raises ValueError if the file isn't an image."""
        pixels = logic.photo_id_pixels(photo)
        return self.session.run(None, {self.input_name: pixels})[0][0]

    def guesses(self, photo: bytes, top: int = 3) -> logic.PhotoGuesses:
        return logic.breed_guesses(self.probabilities(photo), self.class_breeds, top)

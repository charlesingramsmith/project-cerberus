"""Make models/dog_breeds.onnx, the model behind Photo ID.

Run once by hand (the app never runs this; it only loads the .onnx file). It needs
TensorFlow, which the app doesn't, so use a separate virtual environment:

    python -m venv .venv-model
    .venv-model/Scripts/python.exe -m pip install tensorflow-cpu tf2onnx
    .venv-model/Scripts/python.exe scripts/export_photo_id_model.py

It downloads Keras's MobileNetV3Large, trained on ImageNet (1,000 kinds of thing,
including 118 dog breeds, classes 151-268), and saves it in the ONNX format so the app
can run it with the small `onnxruntime` package. The model expects a 224 x 224 RGB photo
with values from 0 to 255 (it scales them itself) and returns 1,000 probabilities.
Which classes are which of our breeds is in data/photo_id_breeds.csv.
"""
from pathlib import Path

import tensorflow as tf
import tf2onnx

OUT = Path(__file__).resolve().parent.parent / "models" / "dog_breeds.onnx"

model = tf.keras.applications.MobileNetV3Large(weights="imagenet", include_preprocessing=True)
spec = (tf.TensorSpec((None, 224, 224, 3), tf.float32, name="image"),)


@tf.function(input_signature=spec)
def classify(image):
    return model(image, training=False)


OUT.parent.mkdir(exist_ok=True)
tf2onnx.convert.from_function(classify, input_signature=spec, opset=17, output_path=str(OUT))
print(f"Saved {OUT} ({OUT.stat().st_size / 1e6:.0f} MB)")

# Models

`dog_breeds.onnx` is the Photo ID model: MobileNetV3Large trained on ImageNet (Keras's
pretrained weights), saved in the ONNX format by `scripts/export_photo_id_model.py`.
About 22 MB. The app runs it with `onnxruntime` in `cerberus/photo_id.py`, and
`data/photo_id_breeds.csv` says which of its dog classes are which of our breeds.

Licence: Keras and its pretrained weights are released under the Apache 2.0 licence.
The weights were trained on ImageNet, whose images are for non-commercial research and
education. That's fine for this free portfolio app; check again before any paid launch.

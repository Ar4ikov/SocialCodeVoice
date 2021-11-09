from keras.models import load_model
import numpy as np
from os import path


class VoiceModel:
    def __init__(self, model_name=None):
        if model_name is None:
            self.model_name = "voice_50_1"

        else:
            self.model_name = model_name

        self.models_path = path.join(path.dirname(__file__), "models")
        self.model = None

        self.key_lists = ["anger", "enthusiasm", "happiness", "sadness", "tiredness",
                          "anger", "enthusiasm", "happiness", "sadness", "tiredness"]

    def load_model(self):
        if not path.isfile(f"{self.models_path}/{self.model_name}/{self.model_name}.h5"):
            raise ValueError(f"There's no model named {self.model_name}")

        self.model = load_model(f"{self.models_path}/{self.model_name}/{self.model_name}.h5")

    def predict_single(self, x):
        if self.model is None:
            raise AttributeError("No model has been loaded.")

        prediction = self.model.predict(np.array([x]))
        return self.key_lists[np.argmax(prediction)]

    def predict_multiple(self, x):
        if self.model is None:
            raise AttributeError("No model has been loaded.")

        emotions_r = []
        prediction = self.model.predict(np.array(x))

        for pred in prediction:
            emotions_r.append(self.key_lists[np.argmax(pred)])

        return emotions_r

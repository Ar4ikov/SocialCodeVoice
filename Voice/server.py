from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
import gevent.pywsgi
from normalization import VoicePreparation
from model import VoiceModel
from os import path, mkdir
from uuid import uuid4 as uuid
from re import match
from time import time


class App(Flask):
    def __init__(self, app_name=__name__):
        super().__init__(app_name)
        self.secret_key = "!TOP_SECRET_KEY"

        self.create_folders()

        self.normalization = VoicePreparation(
            path.join(path.dirname(__file__), "uploads"), path.join(path.dirname(__file__), "images"))

        self.model = VoiceModel("voice_65_1")
        self.model.load_model()

        self.routes()

    @staticmethod
    def create_folders():
        if not path.isdir(path.join(path.dirname(__file__), "uploads")):
            mkdir(path.join(path.dirname(__file__), "uploads"))

        if not path.isdir(path.join(path.dirname(__file__), "images")):
            mkdir(path.join(path.dirname(__file__), "images"))

    def routes(self):
        @self.route("/", methods=["GET"])
        def index():
            return "Hello, World!"

        @self.route("/get_emotion_timeline", methods=["GET", "POST"])
        def get_emotion_timeline():
            if request.method.upper() == "GET":
                return jsonify({
                    "status": False,
                    "error": {
                        "error_code": 1,
                        "error_message": "Method is not allowed."
                    },
                    "executed_time": 0.
                }), 405

            if not request.files:
                return jsonify({
                    "status": False,
                    "error": {
                        "error_code": 2,
                        "error_message": "No file has been uploaded."
                    },
                    "executed_time": 0.
                }), 400

            if len([x for x in request.files]) > 1:
                return jsonify({
                    "status": False,
                    "error": {
                        "error_code": 3,
                        "error_message": "Too much files has been uploaded."
                    },
                    "executed_time": 0.
                }), 400

            if not [x for x in request.files if match(r""".*\.(ogg|mp3)""", request.files[x].filename)]:
                return jsonify({
                    "status": False,
                    "error": {
                        "error_code": 4,
                        "error_message": "Bad file uploaded."
                    },
                    "executed_time": 0.
                }), 400

            file = request.files[[x for x in request.files if match(r""".*\.(ogg|mp3)""", request.files[x].filename)][0]]

            filename = str(uuid())
            file_ext = file.filename.split(".")[-1]
            file.save(f"{self.normalization.upload_dir}/{filename}.{file_ext}")

            time_it_1 = time()

            try:
                x = self.normalization.prepare_multiple_images(filename + "." + file_ext)

            except AssertionError:
                return jsonify({
                    "status": False,
                    "error": {
                        "error_code": 5,
                        "error_message": "No audio signal in file found."
                    },
                    "executed_time": 0.
                }), 400

            else:
                emotions = self.model.predict_multiple(x)
                time_it_2 = time() - time_it_1

                return jsonify({
                    "status": True,
                    "response": {
                        "file_id": filename,
                        "emotions": [{
                            "time_rate": int(self.normalization.sample_rate * 2.5 * (y + 0)), "emotion": z
                        } for y, z in enumerate(emotions)]
                    },
                    "executed_time": round(time_it_2, 3)
                }), 200

        @self.route("/get_emotion", methods=["GET", "POST"])
        def get_emotion():
            if request.method.upper() == "GET":
                return jsonify({
                    "status": False,
                    "error": {
                        "error_code": 1,
                        "error_message": "Method is not allowed."
                    },
                    "executed_time": 0.
                }), 405

            if not request.files:
                return jsonify({
                    "status": False,
                    "error": {
                        "error_code": 2,
                        "error_message": "No file has been uploaded."
                    },
                    "executed_time": 0.
                }), 400

            if len([x for x in request.files]) > 1:
                return jsonify({
                    "status": False,
                    "error": {
                        "error_code": 3,
                        "error_message": "Too much files has been uploaded."
                    },
                    "executed_time": 0.
                }), 400

            if not [x for x in request.files if match(r""".*\.ogg""", request.files[x].filename)]:
                return jsonify({
                    "status": False,
                    "error": {
                        "error_code": 4,
                        "error_message": "Bad file uploaded."
                    },
                    "executed_time": 0.
                }), 400

            file = request.files[[x for x in request.files if match(r""".*\.ogg""", request.files[x].filename)][0]]

            filename = str(uuid())
            file.save(f"{self.normalization.upload_dir}/{filename}.ogg")

            time_it_1 = time()

            try:
                x = self.normalization.prepare_single_image(filename + ".ogg")

            except AssertionError:
                return jsonify({
                    "status": False,
                    "error": {
                        "error_code": 5,
                        "error_message": "No audio signal in file found."
                    },
                    "executed_time": 0.
                }), 400

            else:
                emotion = self.model.predict_single(x)
                time_it_2 = time() - time_it_1

                return jsonify({
                    "status": True,
                    "response": {
                        "file_id": filename,
                        "emotion": emotion
                    },
                    "executed_time": round(time_it_2, 3)
                }), 200

    def run(self, *args, **kwargs):
        super().run(*args, **kwargs, threaded=True)


app_server = gevent.pywsgi.WSGIServer(("0.0.0.0", 8888), App())
app_server.serve_forever()

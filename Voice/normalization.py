import librosa
from librosa.display import specshow
from matplotlib import pyplot as plt
import numpy as np
from PIL import Image
from os import path
from math import ceil


class VoicePreparation:
    def __init__(self, upload_dir, convert_path):
        self.upload_dir = upload_dir
        self.convert_path = convert_path
        self.sample_rate = 22050
        self.duration = 2.5

    def load_voice_sample(self, filename, load_full_sample=False) -> (np.ndarray, int):
        try:
            if not load_full_sample:
                clip, sample_rate = librosa.load(path.join(path.dirname(__file__), self.upload_dir, filename),
                                             sr=self.sample_rate, duration=self.duration, offset=0.0)

            else:
                clip, sample_rate = librosa.load(path.join(path.dirname(__file__), self.upload_dir, filename),
                                                 sr=self.sample_rate, offset=0.0)

        except Exception:
            raise AssertionError("No audio signal in file.")

        else:
            return clip, sample_rate

    def crop_audio_sample(self, clip):
        if self.sample_rate * 2.5 == clip.shape[0]:
            return [clip]

        clips = []
        new_clip = clip.tolist()
        print(len(new_clip))

        base_rate = int(self.sample_rate * self.duration)
        clips_count = len(new_clip) / base_rate

        for x in range(1, ceil(clips_count) + 1):
            clips.append([base_rate * (x - 1), new_clip[base_rate * (x - 1):base_rate * x]])

        clips = [[x, np.array(clip)] for x, clip in clips]
        return clips

    def create_melfcc(self, clip, sample_rate) -> np.ndarray:
        melfcc_s = librosa.feature.melspectrogram(y=clip, sr=sample_rate)
        librosa.display.specshow(librosa.power_to_db(melfcc_s, ref=np.max))

        return melfcc_s

    def make_plot(self, filename, clip, sample_rate, filename_postfix=""):
        fig = plt.figure(figsize=[1.0, 1.0])
        ax = fig.add_subplot(111)

        ax.axes.get_xaxis().set_visible(False)
        ax.axes.get_yaxis().set_visible(False)
        ax.set_frame_on(False)

        melfcc_s = self.create_melfcc(clip, sample_rate)
        filename = filename + filename_postfix + ".jpg"

        plt.savefig(path.join(path.dirname(__file__), self.convert_path, filename),
                    dpi=400, bbox_inches="tight", pad_inches=0)
        plt.close(), fig.clf(), plt.close(fig), plt.close("all")

        del clip, sample_rate, fig, ax, melfcc_s

        return filename

    def convert_voice_to_image(self, filename, single=True):
        plt.interactive(False)

        if single:
            clip, sample_rate = self.load_voice_sample(filename)
        else:
            clip, sample_rate = self.load_voice_sample(filename, load_full_sample=True)

        if not single:
            clips = self.crop_audio_sample(clip)
            filenames = []

            for rate, clip in clips:
                new_filename = self.make_plot(filename, clip, sample_rate, filename_postfix=str(rate))
                filenames.append(new_filename)

            return filenames

        else:
            return self.make_plot(filename, clip, sample_rate)

    def prepare_single_image(self, filename) -> np.ndarray:
        self.convert_voice_to_image(filename)

        img = Image.open(path.join(path.dirname(__file__), self.convert_path, filename + ".jpg"))
        img = img.resize((224, 224))

        return np.asarray(img, dtype="uint8")

    def prepare_multiple_images(self, filename):
        filenames = self.convert_voice_to_image(filename, single=False)
        np_images = []

        for f in filenames:
            img = Image.open(path.join(path.dirname(__file__), self.convert_path, f))
            img = img.resize((224, 224))

            np_images.append(np.asarray(img, dtype="uint8"))

        return np_images

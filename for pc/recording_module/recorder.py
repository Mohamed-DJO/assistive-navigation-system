import cv2
import sounddevice as sd
import numpy as np
from scipy.io.wavfile import write
import threading
import time
import os
import subprocess


class Recorder:
    def init(self, output_folder="recordings"):
        self.output_folder = output_folder
        os.makedirs(self.output_folder, exist_ok=True)

        self.recording = False
        self.frames = []
        self.audio_data = []
        self.fs = 44100
        self._audio_thread = None
        self._lock = threading.Lock()

    def start_recording(self):
        with self._lock:
            if self.recording:
                print("[RECORDER] Already recording.")
                return

            print("[RECORDER] Recording started.")
            self.recording = True
            self.frames = []
            self.audio_data = []

        self._audio_thread = threading.Thread(target=self._record_audio, daemon=True)
        self._audio_thread.start()

    def stop_recording(self):
        with self._lock:
            if not self.recording:
                print("[RECORDER] Not currently recording.")
                return
            self.recording = False

        if self._audio_thread:
            self._audio_thread.join()
            self._audio_thread = None

        if not self.frames:
            print("[RECORDER] No frames captured — skipping save.")
            return

        self._save_files()

    def add_frame(self, frame):
        if self.recording:
            self.frames.append(frame.copy())

    def _record_audio(self):
        def callback(indata, frames, time_info, status):
            if self.recording:
                self.audio_data.append(indata.copy())

        with sd.InputStream(callback=callback, channels=1, samplerate=self.fs):
            while self.recording:
                time.sleep(0.05)

    def _savefiles(self):
        timestamp = time.strftime("%Y%m%d%H%M%S")
        raw_video = os.path.join(self.output_folder, "temp_video.avi")
        raw_audio = os.path.join(self.output_folder, "temp_audio.wav")
        final_output = os.path.join(self.outputfolder, f"recording{timestamp}.mp4")

        # Save video frames
        height, width, _ = self.frames[0].shape
        out = cv2.VideoWriter(
            raw_video,
            cv2.VideoWriter_fourcc(*'XVID'),
            20,
            (width, height)
        )
        for frame in self.frames:
            out.write(frame)
        out.release()

        # Save audio
        if self.audio_data:
            audio_np = np.concatenate(self.audio_data, axis=0)
            write(raw_audio, self.fs, audio_np)
            audio_input = ["-i", raw_audio]
            audio_codec = ["-c:a", "aac"]
        else:
            print("[RECORDER] No audio captured — saving video only.")
            audio_input = []
            audio_codec = ["-an"]

        # Merge with ffmpeg
        cmd = [
            "ffmpeg", "-y",
            "-i", raw_video,
            *audio_input,
            "-c:v", "copy",
            *audio_codec,
            final_output
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Cleanup temp files
        for tmp in [raw_video, raw_audio]:
            if os.path.exists(tmp):
                os.remove(tmp)

        print(f"[RECORDER] Saved: {final_output}")
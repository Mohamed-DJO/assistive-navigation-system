import cv2
import subprocess
import threading
import os
import datetime
import wave

try:
    import pyaudio
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    print("[RECORDER] pyaudio not found — run: pip install pyaudio")

# ✅ Best choice: device 1 (Microphone Array, Realtek) — reliable, 44100Hz, 2ch
# Change to 18 if you prefer the dedicated "Mic input" port
MIC_DEVICE_INDEX = 1
MIC_CHUNK        = 1024


def _detect_mic():
    """
    Auto-detects the default input device and its supported channels/samplerate.
    Returns (device_index, channels, samplerate) or None if no mic found.
    """
    if not AUDIO_AVAILABLE:
        return None
    pa = pyaudio.PyAudio()
    try:
        # Try default input device first
        default = pa.get_default_input_device_info()
        idx      = int(default["index"])
        channels = min(int(default["maxInputChannels"]), 1)  # force mono
        rate     = int(default["defaultSampleRate"])
        print(f"[RECORDER] Auto-detected mic: #{idx} '{default['name']}' "
              f"— {channels}ch @ {rate}Hz")
        return idx, channels, rate
    except Exception as e:
        print(f"[RECORDER] ❌ Mic auto-detect failed: {e}")
        print("[RECORDER] → Run tools/find_mic.py and set MIC_DEVICE_INDEX manually.")
        return None
    finally:
        pa.terminate()


class FFmpegRecorder:
    def __init__(self, output_folder, webcam_name=None, mic_name=None,
                 fps=20, width=640, height=480):
        self.output_folder = output_folder
        self.fps    = fps
        self.width  = width
        self.height = height

        self.process       = None
        self._recording    = False
        self._frames       = []
        self._audio_frames = []
        self._audio_thread = None

        os.makedirs(self.output_folder, exist_ok=True)
        self._ffmpeg_ok = self._check_ffmpeg()

        # ✅ Auto-detect mic settings at init
        # ✅ Use hardcoded values from find_mic.py results
        self._mic_index    = MIC_DEVICE_INDEX
        self._mic_channels = 2       # all your devices report 2 channels
        self._mic_rate     = 44100   # all your devices support 44100Hz

    def _check_ffmpeg(self):
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            return result.returncode == 0
        except FileNotFoundError:
            print("[RECORDER] ❌ ffmpeg not found. Install it and add to PATH.")
            return False

    def start_recording(self):
        if self._recording:
            print("[RECORDER] Already recording.")
            return

        self._recording    = True
        self.process       = True
        self._frames       = []
        self._audio_frames = []

        if AUDIO_AVAILABLE:
            self._audio_thread = threading.Thread(
                target=self._record_audio, daemon=True
            )
            self._audio_thread.start()
        else:
            print("[RECORDER] Audio unavailable — recording video only.")

        print("[RECORDER] Recording started.")

    def stop_recording(self):
        if not self._recording:
            print("[RECORDER] Not recording.")
            return

        self._recording = False
        self.process    = None

        frames_snapshot = list(self._frames)
        audio_thread    = self._audio_thread
        self._audio_thread = None

        print(f"[RECORDER] Stopping: {len(frames_snapshot)} frames captured.")

        if not frames_snapshot:
            print("[RECORDER] No frames — nothing saved.")
            return

        threading.Thread(
            target=self._wait_and_save,
            args=(frames_snapshot, audio_thread),
            daemon=False
        ).start()

    def add_frame(self, frame):
        if not self._recording:
            return
        self._frames.append(cv2.resize(frame, (self.width, self.height)))

    def _record_audio(self):
        pa     = pyaudio.PyAudio()
        stream = None
        try:
            stream = pa.open(
                format=pyaudio.paInt16,
                channels=self._mic_channels,
                rate=self._mic_rate,
                input=True,
                input_device_index=self._mic_index,
                frames_per_buffer=MIC_CHUNK
            )
            print(f"[RECORDER] Audio stream open — "
                  f"device #{self._mic_index}, "
                  f"{self._mic_channels}ch, {self._mic_rate}Hz")
            while self._recording:
                data = stream.read(MIC_CHUNK, exception_on_overflow=False)
                self._audio_frames.append(data)
            print(f"[RECORDER] Audio done: {len(self._audio_frames)} chunks.")
        except Exception as e:
            print(f"[RECORDER] ❌ Audio error: {e}")
            print("[RECORDER] → Run tools/find_mic.py to find the correct device.")
        finally:
            if stream:
                stream.stop_stream()
                stream.close()
            pa.terminate()

    def _wait_and_save(self, frames, audio_thread):
        if audio_thread and audio_thread.is_alive():
            audio_thread.join(timeout=5)

        audio_snapshot = list(self._audio_frames)
        print(f"[RECORDER] Audio chunks collected: {len(audio_snapshot)}")
        self._save(frames, audio_snapshot)

    def _save(self, frames, audio_frames):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        tmp_video = os.path.join(self.output_folder, f"tmp_video_{timestamp}.avi")
        tmp_audio = os.path.join(self.output_folder, f"tmp_audio_{timestamp}.wav")
        final_mp4 = os.path.join(self.output_folder, f"recording_{timestamp}.mp4")

        # --- Write video ---
        h, w, _ = frames[0].shape
        writer = cv2.VideoWriter(
            tmp_video,
            cv2.VideoWriter_fourcc(*"XVID"),
            self.fps, (w, h)
        )
        for f in frames:
            writer.write(f)
        writer.release()

        if not os.path.exists(tmp_video) or os.path.getsize(tmp_video) == 0:
            print("[RECORDER] ❌ Video write failed — aborting.")
            return
        print(f"[RECORDER] Video written: {os.path.getsize(tmp_video)} bytes")

        # --- Write audio ---
        has_audio = bool(audio_frames) and AUDIO_AVAILABLE

        if has_audio:
            try:
                with wave.open(tmp_audio, "wb") as wf:
                    wf.setnchannels(self._mic_channels)
                    wf.setsampwidth(2)
                    wf.setframerate(self._mic_rate)
                    wf.writeframes(b"".join(audio_frames))

                wav_size = os.path.getsize(tmp_audio)
                print(f"[RECORDER] Audio WAV written: {wav_size} bytes.")

                if wav_size < 1000:
                    print("[RECORDER] ⚠️ WAV too small — skipping audio merge.")
                    has_audio = False
            except Exception as e:
                print(f"[RECORDER] ❌ WAV write error: {e}")
                has_audio = False

        # --- ffmpeg merge or video-only ---
        if not has_audio:
            cmd = [
                "ffmpeg", "-y",
                "-i", tmp_video,
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-pix_fmt", "yuv420p", "-an",
                final_mp4
            ]
        else:
            cmd = [
                "ffmpeg", "-y",
                "-i", tmp_video,
                "-i", tmp_audio,
                "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-ar", str(self._mic_rate),
                "-b:a", "128k",
                "-shortest",
                final_mp4
            ]

        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

        if result.returncode == 0:
            print(f"[RECORDER] ✅ Saved: {final_mp4}")
        else:
            print(f"[RECORDER] ❌ ffmpeg failed:\n{result.stderr.decode()}")

        for tmp in [tmp_video, tmp_audio]:
            if os.path.exists(tmp):
                os.remove(tmp)
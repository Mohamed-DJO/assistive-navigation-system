import os
import threading
import json
import queue
import sounddevice as sd
from vosk import Model, KaldiRecognizer
from agent.sos import send_email_alert

# ---------------- SYSTEM STATE ----------------
from agent.state import SYSTEM_STATE   # shared with tts.py to avoid circular import

_last_command = None
_lock         = threading.Lock()

# ---------------- VOSK SETUP ----------------
MODEL_PATH = "models/vosk-model-small-en-us-0.15"

if not os.path.exists(MODEL_PATH):
    raise RuntimeError(
        f"[VOICE] Vosk model not found at '{MODEL_PATH}'.\n"
        f"Download it from https://alphacephei.com/vosk/models "
        f"and extract it to the models/ folder."
    )

model       = Model(MODEL_PATH)
recognizer  = KaldiRecognizer(model, 16000)
audio_queue = queue.Queue()

# ✅ RPi: set to None for auto-detect, or set a number (run `python3 -m sounddevice` to list devices)
# With a Bluetooth headset, pair first, then check which device index appears.
MIC_DEVICE_INDEX = None   # None = default system mic


def _audio_callback(indata, frames, time, status):
    if status:
        print(f"[VOICE] Audio status: {status}")
    audio_queue.put(bytes(indata))


def _listen_loop():
    global _last_command

    stream_kwargs = dict(
        samplerate=16000,
        blocksize=8000,
        dtype="int16",
        channels=1,
        callback=_audio_callback,
    )
    if MIC_DEVICE_INDEX is not None:
        stream_kwargs["device"] = MIC_DEVICE_INDEX

    with sd.RawInputStream(**stream_kwargs):
        print("[VOICE] Listening...")
        while True:
            data = audio_queue.get()
            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                text   = result.get("text", "").lower().strip()
                if text:
                    print(f"[VOICE] Recognized: {text}")
                    with _lock:
                        _last_command = text


def start_listening():
    threading.Thread(target=_listen_loop, daemon=True).start()


def get_last_command():
    global _last_command
    with _lock:
        cmd           = _last_command
        _last_command = None
    return cmd


def process_command(command):
    if not command:
        return None, None

    words = command.strip().split()

    # Strict single-word "stop" only
    if words == ["stop"]:
        SYSTEM_STATE["talking"] = False
        return "Stopping all speech.", None

    if "resume" in command:
        SYSTEM_STATE["talking"] = True
        return "I am active again.", None

    # Recording — always works regardless of talking state
    if "finish" in command and "record" in command:
        return "Recording ended.", "stop_recording"

    if "record" in command:
        return "Recording started.", "start_recording"

    # SOS — always works regardless of talking state
    if "danger" in command or "help" in command or "sos" in command:
        send_email_alert()
        return "Emergency alert sent.", None

    if not SYSTEM_STATE["talking"]:
        return None, None

    if "what is in front" in command:
        return None, "analyze_front"

    if ("guide me" in command or "navigate" in command
            or "take me" in command or "go to" in command):
        return None, "navigate_to"

    if "stop navigation" in command:
        SYSTEM_STATE["talking"] = True
        return None, "stop_navigation"

    return None, None

"""
TTS for Raspberry Pi — uses espeak via subprocess.

Why espeak instead of pyttsx3?
  - pyttsx3 on RPi has threading issues ("run loop already started").
  - espeak is pre-installed on Raspberry Pi OS and works reliably.
  - Audio is routed to the default ALSA/PulseAudio sink, which is your
    Bluetooth speaker once paired and set as default.

To pair your Bluetooth speaker and set it as default:
    bluetoothctl
      power on
      scan on
      pair <MAC>
      connect <MAC>
    # Set as default PulseAudio sink:
    pactl set-default-sink bluez_sink.<MAC_with_underscores>.a2dp_sink

Then espeak will automatically speak through it.

espeak install (if missing):
    sudo apt-get install espeak
"""

import subprocess
import threading
import queue
import time
from agent.state import SYSTEM_STATE   # ✅ no circular import

_speech_queue  = queue.Queue()
_danger_active = threading.Event()

# ✅ Espeak settings — adjust voice/speed to taste
# Voices: en, en-us, en-gb, etc.  Speed: 80–200 (default 160)
ESPEAK_VOICE = "en"
ESPEAK_SPEED = "150"


def _speak_blocking(text):
    """Call espeak synchronously — blocks until speech is done."""
    try:
        subprocess.run(
            ["espeak", "-v", ESPEAK_VOICE, "-s", ESPEAK_SPEED, text],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except FileNotFoundError:
        print("[TTS] ❌ espeak not found. Install with: sudo apt-get install espeak")
    except Exception as e:
        print(f"[TTS] Error: {e}")


def _speak_now(text):
    """
    Force-speak: clears the queue and pushes this message to the front.
    Used for danger alerts and navigation — always plays regardless of SYSTEM_STATE.
    """
    try:
        while True:
            _speech_queue.get_nowait()
    except queue.Empty:
        pass
    _speech_queue.put(("FORCE", text))


def _tts_worker():
    while True:
        item = _speech_queue.get()

        if isinstance(item, tuple):
            # FORCE message — always speak
            _, text = item
            _speak_blocking(text)
        else:
            # Normal message — respect talking state
            if not SYSTEM_STATE["talking"]:
                # Discard remaining queue items too
                try:
                    while True:
                        _speech_queue.get_nowait()
                except queue.Empty:
                    pass
                continue
            _speak_blocking(item)

        time.sleep(0.05)   # tiny pause between utterances


def speak_text(text, priority=False, force=False):
    """
    Queue text for speech.

    force=True  → clears queue, plays immediately (navigation, danger).
    priority=True → clears queue, sets danger_active flag for 3s.
    Otherwise → normal queue.
    """
    if force:
        _speak_now(text)
        return

    if not SYSTEM_STATE["talking"]:
        return

    if priority:
        try:
            while True:
                _speech_queue.get_nowait()
        except queue.Empty:
            pass
        _danger_active.set()
        threading.Timer(3.0, _danger_active.clear).start()

    _speech_queue.put(text)


def is_danger_active():
    return _danger_active.is_set()


# Start the TTS worker thread at import time
threading.Thread(target=_tts_worker, daemon=True).start()

import threading
import queue
import time
from agent.voice_commands import SYSTEM_STATE

_speech_queue  = queue.Queue()
_danger_active = threading.Event()

# ✅ FIX: Single global pyttsx3 engine shared across ALL speech
# pyttsx3 cannot be initialized in multiple threads — causes "run loop already started"
_engine        = None
_engine_lock   = threading.Lock()


def _get_engine():
    # ✅ FIX Bug 1: use lock to make engine creation thread-safe
    global _engine
    with _engine_lock:
        if _engine is None:
            import pyttsx3
            _engine = pyttsx3.init()
            _engine.setProperty("rate", 160)
    return _engine


def _speak_now(text):
    """
    Force-speak by pushing to the front of the queue with a special marker.
    ✅ FIX: No longer creates a new pyttsx3 instance in a separate thread.
    The single TTS worker handles everything — no 'run loop already started'.
    """
    # Clear queue first so force messages play immediately
    try:
        while True:
            _speech_queue.get_nowait()
    except queue.Empty:
        pass
    _speech_queue.put(("FORCE", text))


def _tts_worker():
    engine = _get_engine()

    while True:
        item = _speech_queue.get()

        # Unpack (force flag, text) or plain string for backward compat
        if isinstance(item, tuple):
            _, text = item
        else:
            text = item

        if not SYSTEM_STATE["talking"] and not isinstance(item, tuple):
            try:
                while True:
                    _speech_queue.get_nowait()
            except queue.Empty:
                pass
            continue

        try:
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            print(f"[TTS] Error: {e}")
            # ✅ Re-init engine if it crashes
            try:
                import pyttsx3
                global _engine
                _engine = pyttsx3.init()
                _engine.setProperty("rate", 160)
                engine = _engine
            except Exception as reinit_err:
                print(f"[TTS] Re-init failed: {reinit_err}")

        time.sleep(0.1)


def speak_text(text, priority=False, force=False):
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


threading.Thread(target=_tts_worker, daemon=True).start()
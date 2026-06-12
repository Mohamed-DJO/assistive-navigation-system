"""
Raspberry Pi — Assistive Navigation AI
Full integration: camera, YOLO, danger alerts, TTS (espeak → BT speaker),
voice commands (Vosk), SOS email, GPS navigation, recording (no ffmpeg).

Install:
    pip install pyaudio vosk sounddevice requests ultralytics supervision
    sudo apt-get install espeak python3-pyaudio portaudio19-dev
"""

import cv2
import time
import threading
from picamera2 import Picamera2

from vision.yolo_vision import analyze_frame, init_model
from voice.tts import speak_text, is_danger_active
from agent.danger import detect_danger
from agent.voice_commands import (
    start_listening, get_last_command, process_command, SYSTEM_STATE
)
from recording_module.pi_recorder import PiRecorder
from navigation.navigator import Navigator
#from navigation.gps.gps_pc import PCGPS
from navigation.gps.gps_neo7m import Neo7MGPS
from navigation.places import find_place

# ---------------- CONFIG ----------------
FRAME_WIDTH   = 320
FRAME_HEIGHT  = 240
FRAME_SKIP    = 2
SPEAK_DELAY   = 4
SHOW_DISPLAY  = True    # set False for headless (no monitor)
OUTPUT_FOLDER = "recordings"


# ---------------- BEEP (Linux / RPi) ----------------
def _beep():
    def _play():
        try:
            import subprocess
            subprocess.run(
                ["speaker-test", "-t", "sine", "-f", "880", "-l", "1", "-s", "1"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=1
            )
        except Exception:
            pass
    threading.Thread(target=_play, daemon=True).start()


# ---------------- INIT ----------------
print("[MAIN] Loading YOLO model...")
init_model()
print("[MAIN] Model loaded.")

start_listening()

#gps       = PCGPS()
gps = Neo7MGPS()
navigator = Navigator(speak_fn=speak_text, gps=gps)
recorder  = PiRecorder(
    output_folder=OUTPUT_FOLDER,
    fps=20,
    width=FRAME_WIDTH,
    height=FRAME_HEIGHT
)

picam2 = Picamera2()
config = picam2.create_preview_configuration(
    main={"format": "RGB888", "size": (FRAME_WIDTH, FRAME_HEIGHT)}
)
picam2.configure(config)
picam2.start()
time.sleep(2)
print("[MAIN] Camera started.")


# ---------------- ACTION HANDLER ----------------
def handle_action(action, command):
    if action == "start_recording":
        if recorder.active:
            speak_text("Already recording.", force=True)
        else:
            recorder.start_recording()
            speak_text("Recording started.", force=True)

    elif action == "stop_recording":
        if recorder.active:
            recorder.stop_recording()
            speak_text("Recording saved.", force=True)
        else:
            speak_text("No active recording.", force=True)

    elif action == "navigate_to":
        place, key = find_place(command)
        if place:
            lat, lon = gps.get_location()
            if lat is None:
                speak_text("Could not get your location.", force=True)
            else:
                speak_text(f"Getting route to {place['name']}.", force=True)
                navigator.start(lat, lon, place["lat"], place["lon"], place["name"])
        else:
            speak_text("Sorry, I do not know that place.", force=True)

    elif action == "stop_navigation":
        navigator.stop()

    elif action == "analyze_front":
        pass


# ---------------- MAIN LOOP ----------------
def main():
    last_spoken_time  = 0
    spoken_cache      = set()
    frame_count       = 0
    objects           = []
    annotated_frame   = None
    prev_objects      = []
    camera_fail_count = 0
    fps_counter       = 0
    fps_timer         = time.time()
    current_fps       = 0

    speak_text("Assistive navigation system ready.", force=True)
    print("[MAIN] Running. Press ESC to quit.")

    try:
        while True:
            frame = picam2.capture_array()

            if frame is None:
                camera_fail_count += 1
                if camera_fail_count % 30 == 1:
                    print(f"[ERROR] Camera read failed ({camera_fail_count}x).")
                if camera_fail_count == 30:
                    speak_text("Warning. Camera disconnected.", force=True)
                time.sleep(0.1)
                continue

            camera_fail_count = 0
            frame_count += 1

            # FPS counter
            fps_counter += 1
            if time.time() - fps_timer >= 1.0:
                current_fps = fps_counter
                fps_counter = 0
                fps_timer   = time.time()

            # Voice commands
            command = get_last_command()
            if command:
                response_text, action = process_command(command)
                if response_text:
                    speak_text(response_text)
                handle_action(action, command)

            # YOLO inference
            if frame_count % FRAME_SKIP == 0:
                try:
                    annotated_frame, objects = analyze_frame(frame)
                    if objects:
                        prev_objects = objects
                except Exception as e:
                    print(f"[YOLO ERROR] {e}")
                    time.sleep(0.1)
                    annotated_frame = frame
                    objects         = prev_objects

                current_time   = time.time()

                danger_message = detect_danger(objects)
                if danger_message:
                    speak_text(danger_message, priority=True)
                    _beep()
                    last_spoken_time = current_time

                elif (objects
                      and SYSTEM_STATE["talking"]
                      and not navigator.active
                      and not is_danger_active()
                      and (current_time - last_spoken_time > SPEAK_DELAY)):

                    messages = []
                    for obj in objects:
                        key = f"{obj['name']}_{obj['position']}_{round(obj['distance'], 1)}"
                        if key not in spoken_cache:
                            messages.append(
                                f"{obj['name'].capitalize()} at "
                                f"{obj['distance']:.1f} meters {obj['position']}"
                            )
                            spoken_cache.add(key)

                    if messages:
                        speak_text(". ".join(messages))
                        last_spoken_time = current_time

                if objects:
                    active_keys = {
                        f"{o['name']}_{o['position']}_{round(o['distance'], 1)}"
                        for o in objects
                    }
                    spoken_cache.intersection_update(active_keys)

            # Build display frame
            display = annotated_frame if annotated_frame is not None else frame
            overlay = display.copy()
            ts_str  = time.strftime("%H:%M:%S")
            cv2.putText(overlay, f"FPS: {current_fps}", (5, 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
            cv2.putText(overlay, ts_str, (5, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)

            # Red REC indicator when recording
            if recorder.active:
                cv2.circle(overlay, (FRAME_WIDTH - 15, 15), 6, (0, 0, 255), -1)
                cv2.putText(overlay, "REC", (FRAME_WIDTH - 45, 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)

            recorder.add_frame(overlay)

            if SHOW_DISPLAY:
                cv2.imshow("Assistive Navigation AI", overlay)
                if cv2.waitKey(1) == 27:
                    break
            else:
                if frame_count % 60 == 0:
                    print(f"[MAIN] FPS: {current_fps} | "
                          f"Objects: {len(objects)} | "
                          f"Recording: {recorder.active}")

    finally:
        if recorder.active:
            recorder.stop_recording()
        if navigator.active:
            navigator.stop()
        picam2.stop()
        if SHOW_DISPLAY:
            cv2.destroyAllWindows()
        print("[MAIN] Done.")


if __name__ == "__main__":
    main()

import cv2
import time
import threading
from vision.yolo_vision import analyze_frame, init_model
from voice.tts import speak_text, is_danger_active
from agent.danger import detect_danger
from agent.voice_commands import (
    start_listening, get_last_command, process_command, SYSTEM_STATE
)
from recording_module.ffmpeg_recorder import FFmpegRecorder
from navigation.navigator import Navigator
from navigation.gps.gps_pc import PCGPS
from navigation.places import find_place

# ---------------- CONFIG ----------------
FRAME_WIDTH   = 320
FRAME_HEIGHT  = 240
FRAME_SKIP    = 2
SPEAK_DELAY   = 4
OUTPUT_FOLDER = "C:/Users/Mohamed pc/OneDrive/Documents/PFE/Claude exemple 4/recorded_videos" #CHANGE THIS TO YOUR DESIRED FOLDER

# ✅ Improvement 4: beep sound for danger using winsound (Windows built-in)
# Runs in a thread so it never blocks the main loop
def _beep():
    def _play():
        try:
            import winsound
            winsound.Beep(880, 200)   # 880Hz, 200ms
        except Exception:
            pass  # beep is optional — never crash the main loop
    threading.Thread(target=_play, daemon=True).start()

# ---------------- INIT ----------------
start_listening()
init_model()

gps       = PCGPS()
navigator = Navigator(speak_fn=speak_text, gps=gps)
recorder  = FFmpegRecorder(
    output_folder=OUTPUT_FOLDER,
    fps=20,
    width=FRAME_WIDTH,
    height=FRAME_HEIGHT
)


def handle_action(action, command):
    if action == "start_recording":
        if recorder.process is None:
            recorder.start_recording()
            speak_text("Recording started.", force=True)
        else:
            speak_text("Already recording.", force=True)

    elif action == "stop_recording":
        if recorder.process is not None:
            recorder.stop_recording()
            speak_text("Recording ended.", force=True)
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


def main():
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

    last_spoken_time   = 0
    spoken_cache       = set()
    frame_count        = 0
    objects            = []
    annotated_frame    = None
    prev_objects       = []
    camera_fail_count  = 0
    fps_counter        = 0
    fps_timer          = time.time()
    current_fps        = 0

    # ✅ Improvement 1: startup voice confirmation
    speak_text("Assistive navigation system ready.", force=True)
    print("[MAIN] Assistive Navigation AI running. Press ESC to quit.")

    while True:
        ret, frame = cap.read()

        # ✅ Bug 3 + Improvement 2: camera failure with counter and voice alert
        if not ret:
            camera_fail_count += 1
            if camera_fail_count % 30 == 1:   # alert every ~3s of failure
                print(f"[ERROR] Camera read failed ({camera_fail_count} times).")
            if camera_fail_count == 30:
                speak_text("Warning. Camera disconnected.", force=True)
            time.sleep(0.1)
            continue

        camera_fail_count = 0  # reset on success
        frame_count += 1

        # ✅ Improvement 5: FPS calculation
        fps_counter += 1
        if time.time() - fps_timer >= 1.0:
            current_fps = fps_counter
            fps_counter = 0
            fps_timer   = time.time()

        frame = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT))

        # ✅ Voice commands every frame — independent of YOLO
        command = get_last_command()
        if command:
            response_text, action = process_command(command)
            if response_text:
                speak_text(response_text)
            handle_action(action, command)

        if frame_count % FRAME_SKIP == 0:
            try:
                annotated_frame, objects = analyze_frame(frame)
                if objects:
                    prev_objects = objects
            except Exception as e:
                # ✅ Bug 3: throttle YOLO error logs + small sleep to avoid flood
                print(f"[YOLO ERROR] {e}")
                time.sleep(0.1)
                annotated_frame = frame
                objects         = prev_objects  # keep last valid detections

            current_time   = time.time()
            danger_message = detect_danger(objects)

            if danger_message:
                speak_text(danger_message, priority=True)
                _beep()   # ✅ Improvement 4: beep on danger
                last_spoken_time = current_time

            # ✅ Improvement 3: skip object speech during navigation
            elif (objects
                  and SYSTEM_STATE["talking"]
                  and not navigator.active       # ✅ navigation takes priority
                  and not is_danger_active()
                  and (current_time - last_spoken_time > SPEAK_DELAY)):

                messages = []
                for obj in objects:
                    # ✅ Bug 4: include rounded distance in cache key
                    # prevents two cars at different distances sharing the same key
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

        # ✅ Improvement 5: overlay FPS + timestamp on display frame
        display = annotated_frame if annotated_frame is not None else frame
        overlay = display.copy()
        ts_str  = time.strftime("%H:%M:%S")
        cv2.putText(overlay, f"FPS: {current_fps}", (5, 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
        cv2.putText(overlay, ts_str, (5, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)

        recorder.add_frame(overlay)
        cv2.imshow("Assistive Navigation AI", overlay)

        if cv2.waitKey(1) == 27:
            break

    if recorder.process is not None:
        recorder.stop_recording()
    if navigator.active:
        navigator.stop()

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
import requests
import threading
import time
import json
import math

VALHALLA_URL       = "http://localhost:8002/route"
WAYPOINT_RADIUS_M  = 300    # meters — matches IP GPS accuracy (~200-500m)
GPS_POLL_INTERVAL  = 3      # seconds between GPS checks
STEP_TIMEOUT_S     = 60     # seconds — move to next step even if GPS not close enough


def decode_polyline(encoded):
    """Decode Valhalla encoded polyline into list of (lat, lon) tuples."""
    coords = []
    index, lat, lng = 0, 0, 0
    while index < len(encoded):
        for is_lng in (False, True):
            shift, result = 0, 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else result >> 1
            if is_lng:
                lng += delta
                coords.append((lat / 1e6, lng / 1e6))
            else:
                lat += delta
    return coords


def haversine(lat1, lon1, lat2, lon2):
    """Returns distance in meters between two GPS coordinates."""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi    = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class Navigator:
    def __init__(self, speak_fn, gps):
        self.speak   = speak_fn
        self.gps     = gps
        self.active  = False
        self._thread = None
        self._destination_name = None
        self._steps     = []
        self._waypoints = []

    def start(self, origin_lat, origin_lon, dest_lat, dest_lon, dest_name="destination"):
        result = self._get_route(origin_lat, origin_lon, dest_lat, dest_lon)
        if not result:
            self.speak("Sorry, I could not find a route.", force=True)
            return

        self._steps, self._waypoints = result
        self.active = True
        self._destination_name = dest_name

        total_m = sum(s["length"] for s in self._steps)
        self.speak(
            f"Starting navigation to {dest_name}. "
            f"{len(self._steps)} steps, {total_m} meters total.",
            force=True
        )

        self._thread = threading.Thread(target=self._navigate_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.active = False
        self.speak("Navigation stopped.", force=True)

    def _get_route(self, from_lat, from_lon, to_lat, to_lon):
        try:
            payload = {
                "locations": [
                    {"lat": from_lat, "lon": from_lon},
                    {"lat": to_lat,   "lon": to_lon}
                ],
                "costing": "pedestrian",
                "directions_options": {"language": "en-US"}
            }
            response = requests.post(VALHALLA_URL, json=payload, timeout=10)
            data = response.json()

            if "trip" not in data:
                print(f"[NAV] Valhalla error: {data}")
                return None

            leg       = data["trip"]["legs"][0]
            waypoints = decode_polyline(leg["shape"])
            steps     = []
            for m in leg["maneuvers"]:
                steps.append({
                    "instruction":    m.get("instruction", ""),
                    "length":         round(m.get("length", 0) * 1000),
                    "time":           round(m.get("time", 0)),
                    "waypoint_index": m.get("begin_shape_index", 0),
                })

            print(f"[NAV] Route: {len(steps)} steps, {len(waypoints)} waypoints.")
            return steps, waypoints

        except Exception as e:
            print(f"[NAV] Route error: {e}")
            return None

    def _navigate_loop(self):
        step_index = 0

        while self.active and step_index < len(self._steps):
            step        = self._steps[step_index]
            instruction = step["instruction"]
            length      = step["length"]
            est_time    = step["time"]

            msg = f"{instruction} Continue for {length} meters." if length >= 10 else instruction
            print(f"[NAV] Step {step_index+1}/{len(self._steps)}: {msg}")
            self.speak(msg, force=True)

            # Target waypoint = start of NEXT step (or last waypoint for final step)
            if step_index + 1 < len(self._steps):
                target_idx = self._steps[step_index + 1]["waypoint_index"]
            else:
                target_idx = len(self._waypoints) - 1

            target_lat, target_lon = self._waypoints[target_idx]

            # Wait until GPS is close enough OR timeout expires
            step_start   = time.time()
            timeout      = max(est_time * 2, STEP_TIMEOUT_S)
            reached      = False

            while self.active:
                elapsed = time.time() - step_start

                lat, lon = self.gps.get_location()
                if lat is not None and lon is not None:
                    dist = haversine(lat, lon, target_lat, target_lon)
                    print(f"[NAV] Step {step_index+1} — dist: {dist:.0f}m, "
                          f"elapsed: {elapsed:.0f}s / timeout: {timeout:.0f}s")

                    if dist <= WAYPOINT_RADIUS_M:
                        print(f"[NAV] Waypoint reached (GPS).")
                        reached = True
                        break

                if elapsed >= timeout:
                    print(f"[NAV] Timeout — moving to next step.")
                    break

                time.sleep(GPS_POLL_INTERVAL)

            step_index += 1

        if self.active:
            self.speak(f"You have arrived at {self._destination_name}.", force=True)
            self.active = False
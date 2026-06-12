import time

DANGER_RULES = {
    "person":     1.5,
    "car":        5.0,
    "bus":        6.0,
    "motorcycle": 4.0,
    "stairs":     2.0
}

# ✅ FIX 12: Per-object cooldown tracker — prevents repeating same warning every 2s
_last_alert_times = {}
COOLDOWN_PER_OBJECT = 6.0   # seconds between alerts for the same object type


def detect_danger(objects):
    """
    Returns the most critical danger message (closest dangerous object),
    or None if no danger detected or all dangers are on cooldown.
    """
    now = time.time()
    worst = None
    worst_ratio = None

    for obj in objects:
        name     = obj["name"]
        distance = obj["distance"]
        position = obj["position"]

        if name not in DANGER_RULES:
            continue

        threshold = DANGER_RULES[name]
        if distance > threshold:
            continue

        # ✅ FIX 12: Skip if this object type was recently alerted
        last_alerted = _last_alert_times.get(name, 0)
        if now - last_alerted < COOLDOWN_PER_OBJECT:
            continue

        # ✅ FIX 17: Exponential weighting — very close objects get much higher priority
        ratio = (distance / threshold) ** 2

        if worst_ratio is None or ratio < worst_ratio:
            worst_ratio = ratio
            # ✅ FIX 15: Natural, professional phrasing for accessibility
            worst = (name, f"Warning. {name.capitalize()} is very close {position}.")

    if worst:
        name, message = worst
        _last_alert_times[name] = now   # record alert time
        return message

    return None
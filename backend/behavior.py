import time

entry_times = {}

LOITER_TIME = 10  # seconds

def detect_loitering(tracks):
    alerts = []

    current_time = time.time()

    for track_id, x, y, w, h in tracks:
        if track_id not in entry_times:
            entry_times[track_id] = current_time

        duration = current_time - entry_times[track_id]

        if duration > LOITER_TIME:
            alerts.append((track_id, duration))

    return alerts
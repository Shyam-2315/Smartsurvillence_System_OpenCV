import time

entry_times = {}

LOITER_TIME = 10  # seconds
STALE_TRACK_TIMEOUT = 3  # seconds

def detect_loitering(tracks):
    alerts = []

    current_time = time.time()
    current_ids = {track_id for track_id, *_ in tracks}

    # Cleanup stale tracks so old IDs don't grow forever.
    stale_ids = [
        track_id
        for track_id in entry_times
        if track_id not in current_ids and (current_time - entry_times[track_id]) > STALE_TRACK_TIMEOUT
    ]
    for track_id in stale_ids:
        entry_times.pop(track_id, None)

    for track_id, x, y, w, h in tracks:
        if track_id not in entry_times:
            entry_times[track_id] = current_time

        duration = current_time - entry_times[track_id]

        if duration > LOITER_TIME:
            alerts.append((track_id, duration))

    return alerts
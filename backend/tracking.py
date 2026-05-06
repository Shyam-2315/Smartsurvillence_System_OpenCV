from deep_sort_realtime.deepsort_tracker import DeepSort

tracker = DeepSort(max_age=30)

def track_objects(detections, frame):
    tracks = tracker.update_tracks(detections, frame=frame)

    results = []

    for track in tracks:
        if not track.is_confirmed():
            continue

        track_id = track.track_id
        l, t, w, h = map(int, track.to_ltrb())

        results.append((track_id, l, t, w, h))

    return results
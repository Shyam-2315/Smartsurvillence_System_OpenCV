from deep_sort_realtime.deepsort_tracker import DeepSort

# Initialize tracker
tracker = DeepSort(
    max_age=30,
    n_init=2
)


def track_objects(detections, frame):

    tracks = tracker.update_tracks(
        detections,
        frame=frame
    )

    results = []

    for track in tracks:

        if not track.is_confirmed():
            continue

        track_id = track.track_id

        # Correct coordinates
        left, top, right, bottom = map(
            int,
            track.to_ltrb()
        )

        width = right - left
        height = bottom - top

        results.append((
            track_id,
            left,
            top,
            width,
            height
        ))

    return results
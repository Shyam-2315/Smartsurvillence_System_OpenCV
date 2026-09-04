"""Pure alert-debouncing policy used by the shared AI worker."""
def should_create_incident(track_id: int, alerted_track_ids: set, last_incident_ts: dict, now_ts: float, cooldown_sec: float) -> bool:
    # A continuously visible track yields one incident. It becomes eligible again only after
    # the worker forgets the track on disappearance, preventing per-frame alert storms.
    if track_id in alerted_track_ids:
        return False
    return now_ts - float(last_incident_ts.get(track_id, 0)) >= max(0.0, cooldown_sec)

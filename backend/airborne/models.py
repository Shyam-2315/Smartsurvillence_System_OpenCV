"""Domain constants shared by mission services and API schemas."""

MISSION_SOURCE_TYPES = {"live", "recorded"}
MISSION_STATUSES = {"planned", "active", "completed", "aborted"}
MISSION_EVENT_TYPES = {
    "mission_started", "mission_completed", "mission_aborted", "object_detected",
    "incident_created", "manual_capture", "evidence_created", "visual_analysis_created",
    "video_lost", "video_restored", "telemetry_stale", "telemetry_restored",
    "recorded_detection",
}
VALID_TRANSITIONS = {
    "planned": {"active": "mission_started"},
    "active": {"completed": "mission_completed", "aborted": "mission_aborted"},
    "completed": {},
    "aborted": {},
}


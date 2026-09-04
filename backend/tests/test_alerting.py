import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from alerting import should_create_incident

def test_new_track_is_eligible_after_cooldown_window():
    assert should_create_incident(1, set(), {}, 100, 30)
    assert not should_create_incident(1, set(), {1: 90}, 100, 30)

def test_persistent_alerted_track_never_repeats_per_frame():
    assert not should_create_incident(1, {1}, {1: 1}, 1000, 30)

def test_zero_cooldown_allows_first_incident():
    assert should_create_incident(5, set(), {}, 1, 0)

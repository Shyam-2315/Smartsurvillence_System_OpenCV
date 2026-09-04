import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import behavior

def test_loitering_requires_duration(monkeypatch):
    behavior.entry_times.clear(); clock=iter([100, 105, 111]); monkeypatch.setattr(behavior.time, "time", lambda: next(clock))
    tracks=[(7, 1, 1, 10, 10)]
    assert behavior.detect_loitering(tracks, 10) == []
    assert behavior.detect_loitering(tracks, 10) == []
    assert behavior.detect_loitering(tracks, 10) == [(7, 11)]

def test_loitering_forgets_stale_track(monkeypatch):
    behavior.entry_times.clear(); behavior.entry_times[1]=1; monkeypatch.setattr(behavior.time, "time", lambda: 10)
    behavior.detect_loitering([])
    assert 1 not in behavior.entry_times

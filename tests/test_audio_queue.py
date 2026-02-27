import time
from pathlib import Path
from unittest.mock import MagicMock
from radar.audio import AudioEngine

def test_audio_queue_delays():
    # Setup
    sound_dir = Path("sound")
    delays = {
        "level_0": 0.1,  # Short delays for testing
        "level_1": 0.2,
    }
    engine = AudioEngine(sound_dir, enabled=True, delays=delays)
    engine.play = MagicMock() # Don't actually play audio
    
    # Mock event
    event1 = MagicMock()
    event1.id = "ev1"
    event1.magnitude = 2.5 # level_0
    
    event2 = MagicMock()
    event2.id = "ev2"
    event2.magnitude = 4.0 # level_1
    
    # Queue events
    engine.queue_earthquake(event1)
    engine.queue_earthquake(event2)
    
    # First tick should release event1 immediately
    released, felt = engine.tick()
    assert len(released) == 1
    assert released[0].id == "ev1"
    assert not felt
    engine.play.assert_called_with("level_0")
    
    # Second tick immediately after should not release anything (delay)
    released, felt = engine.tick()
    assert len(released) == 0
    
    # Wait for delay
    time.sleep(0.15)
    
    # Third tick should release event2
    released, felt = engine.tick()
    assert len(released) == 1
    assert released[0].id == "ev2"
    engine.play.assert_called_with("level_1")

def test_felt_queue():
    engine = AudioEngine(Path("sound"), delays={"felt": 0.1})
    engine.play = MagicMock()
    
    engine.queue_felt()
    
    released, felt = engine.tick()
    assert len(released) == 0
    assert felt is True
    engine.play.assert_called_with("felt")

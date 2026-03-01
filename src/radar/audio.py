"""
Audio engine — UI sound effects and earthquake alert playback.

Uses miniaudio for low-latency, thread-safe WAV/MP3 playback.
Sounds are pre-loaded into memory for instant triggering.
"""

from __future__ import annotations

import array
import logging
import time
import threading
from collections import deque
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from radar.data.earthquake import EarthquakeEvent

logger = logging.getLogger(__name__)

try:
    import miniaudio
    _HAS_AUDIO = True
except ImportError:
    _HAS_AUDIO = False
    logger.debug("miniaudio not available — audio disabled")

_SAMPLE_RATE = 44100
_NCHANNELS = 2


class AudioEngine:
    """Manages UI sound effects with pre-loaded audio buffers.

    Usage:
        engine = AudioEngine(sound_dir, volume=0.7)
        engine.start()
        engine.play("click")
        ...
        engine.stop()
    """

    # Map of logical sound names to filenames (checked in order)
    _SOUND_FILES: dict[str, list[str]] = {
        "click":    ["click.mp3", "click.wav"],
        "unclick":  ["unclick.mp3", "unclick.wav"],
        "level_0":  ["level_0.wav", "level_0.mp3"],
        "level_1":  ["level_1.wav", "level_1.mp3"],
        "level_2":  ["level_2.wav", "level_2.mp3"],
        "level_3":  ["level_3.wav", "level_3.mp3"],
        "felt":     ["felt.wav", "felt.mp3"],
        "update":   ["update.mp3", "update.wav"],
    }

    def __init__(
        self,
        sound_dirs: list[Path],
        volume: float = 0.7,
        enabled: bool = True,
        delays: dict[str, float] | None = None,
    ) -> None:
        self._sound_dirs = sound_dirs
        self._volume = max(0.0, min(1.0, volume))
        self._enabled = enabled and _HAS_AUDIO
        self._lock = threading.Lock()
        
        # Delay management
        self._delays = delays or {}
        self._event_queue: deque[tuple[str, Any]] = deque()
        self._next_release_time = 0.0

        # Pre-decoded audio: name -> array.array("h", ...) of int16 samples
        self._buffers: dict[str, array.array] = {}

        # Active sounds: list of [samples_array, offset]
        self._active: list[list] = []

    def start(self) -> None:
        """Pre-load sounds and start the audio device."""
        if not self._enabled:
            logger.info("Audio engine disabled")
            return

        self._load_sounds()

        if not self._buffers:
            logger.warning("No sound files found in %s — audio disabled", self._sound_dirs)
            self._enabled = False
            return

        try:
            self._device = miniaudio.PlaybackDevice(
                output_format=miniaudio.SampleFormat.SIGNED16,
                nchannels=_NCHANNELS,
                sample_rate=_SAMPLE_RATE,
                buffersize_msec=200,
            )
            gen = self._stream_generator()
            next(gen)  # Prime the generator
            self._device.start(gen)
            logger.info(
                "Audio engine started — %d sounds loaded, volume=%.0f%%",
                len(self._buffers), self._volume * 100,
            )
        except Exception as e:
            logger.error("Failed to start audio device: %s", e)
            self._enabled = False

    def _load_sounds(self) -> None:
        """Scan sound directories and decode all found audio files."""
        # Prioritize sounds found in later directories (user overrides)
        for directory in self._sound_dirs:
            if not directory.exists():
                continue

            for name, candidates in self._SOUND_FILES.items():
                for filename in candidates:
                    path = directory / filename
                    if path.exists():
                        try:
                            decoded = miniaudio.decode_file(
                                str(path),
                                output_format=miniaudio.SampleFormat.SIGNED16,
                                nchannels=_NCHANNELS,
                                sample_rate=_SAMPLE_RATE,
                            )
                            # Store as int16 array for fast slicing (overwrites internal if found in external)
                            self._buffers[name] = array.array("h", decoded.samples)
                            logger.debug("Loaded sound: %s (%s, %d samples)", name, filename, len(decoded.samples))
                            break  # Stop checking candidates for THIS directory
                        except Exception as e:
                            logger.warning("Failed to decode %s: %s", filename, e)
                            # Don't break here, try next candidate

    def _stream_generator(self):
        """Audio stream generator — yields mixed audio frames forever."""
        required_frames = yield b""  # Prime point

        while True:
            frames = required_frames or 1024
            num_samples = frames * _NCHANNELS

            with self._lock:
                if not self._active:
                    # Fast path: silence when nothing is playing
                    required_frames = yield b"\x00" * (num_samples * 2)
                    continue

                # Start with silence
                out = array.array("h", bytes(num_samples * 2))
                still_active = []

                for entry in self._active:
                    src = entry[0]       # array.array of int16 samples
                    offset = entry[1]    # current offset in samples
                    remaining = len(src) - offset

                    if remaining <= 0:
                        continue

                    copy_count = min(num_samples, remaining)

                    # Bulk slice + volume-adjusted mix
                    chunk = src[offset:offset + copy_count]
                    vol = self._volume
                    for i in range(copy_count):
                        mixed = out[i] + int(chunk[i] * vol)
                        if mixed > 32767:
                            out[i] = 32767
                        elif mixed < -32768:
                            out[i] = -32768
                        else:
                            out[i] = mixed

                    entry[1] = offset + copy_count
                    if entry[1] < len(src):
                        still_active.append(entry)

                self._active = still_active

            required_frames = yield out.tobytes()

    def play(self, name: str) -> None:
        """Trigger a sound by logical name. Non-blocking, thread-safe."""
        if not self._enabled or name not in self._buffers:
            return

        samples = self._buffers[name]

        with self._lock:
            # Limit concurrent sounds to prevent overload
            if len(self._active) > 6:
                self._active = self._active[-4:]
            self._active.append([samples, 0])

    def play_for_magnitude(self, magnitude: float) -> None:
        """Play the appropriate level sound based on earthquake magnitude."""
        if magnitude < 3.0:
            self.play("level_0")
        elif magnitude < 5.0:
            self.play("level_1")
        elif magnitude < 7.0:
            self.play("level_2")
        else:
            self.play("level_3")

    def play_felt(self) -> None:
        """Play the 'felt' alert sound."""
        self.play("felt")

    def queue_earthquake(self, event: EarthquakeEvent) -> None:
        """Add an earthquake event to the playback queue."""
        self._event_queue.append(("earthquake", event))

    def queue_felt(self) -> None:
        """Add a 'felt' alert to the playback queue."""
        self._event_queue.append(("felt", None))

    def queue_update(self) -> None:
        """Add an update tick to the playback queue."""
        self._event_queue.append(("update", None))

    def tick(self) -> tuple[list[EarthquakeEvent], bool]:
        """Update the queue state and release events when delays expire.
        
        Returns:
            tuple: (list of released EarthquakeEvents, bool if felt alert was triggered)
        """
        released = []
        felt_triggered = False
        if not self._event_queue:
            return released, felt_triggered

        now = time.monotonic()
        if now < self._next_release_time:
            return released, felt_triggered

        # Release the next item from the queue
        item_type, data = self._event_queue.popleft()
        delay = 0.0

        if item_type == "earthquake":
            mag = data.magnitude
            if mag < 3.0:
                self.play("level_0")
                delay = self._delays.get("level_0", 1.2)
            elif mag < 5.0:
                self.play("level_1")
                delay = self._delays.get("level_1", 1.7)
            elif mag < 7.0:
                self.play("level_2")
                delay = self._delays.get("level_2", 2.3)
            else:
                self.play("level_3")
                delay = self._delays.get("level_3", 2.3)
            released.append(data)
            
        elif item_type == "felt":
            self.play_felt()
            delay = self._delays.get("felt", 9.0)
            felt_triggered = True
            
        elif item_type == "update":
            self.play("update")
            delay = self._delays.get("update", 0.5)

        self._next_release_time = now + delay
        return released, felt_triggered

    def set_volume(self, volume: float) -> None:
        """Set the master volume (0.0 to 1.0)."""
        self._volume = max(0.0, min(1.0, volume))

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable audio playback."""
        self._enabled = enabled and _HAS_AUDIO

    def stop(self) -> None:
        """Stop the audio device and release resources."""
        if self._device:
            try:
                self._device.close()
            except Exception:
                pass
            self._device = None
        with self._lock:
            self._active.clear()
        self._buffers.clear()
        logger.info("Audio engine stopped")

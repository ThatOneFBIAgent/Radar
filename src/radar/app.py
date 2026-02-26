"""
Main application orchestrator — wires data, UI, and theme systems.

Manages the async data fetching loop, DearPyGui render loop,
and coordinates updates between all components.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime, timezone
from queue import Empty, Queue
from typing import Any

import dearpygui.dearpygui as dpg

from radar.config import RadarConfig, THEMES_DIR, SOUND_DIR
from radar.audio import AudioEngine
from radar.data.earthquake import EarthquakeDiff, EarthquakeEvent, EarthquakeFetcher
from radar.data.weather import WeatherData, WeatherFetcher
from radar.data.cities import CityIndex
from radar.themes.loader import ThemeData, apply_theme, load_theme, get_available_themes
from radar.themes.watcher import ThemeWatcher
from radar.ui.layout import LayoutManager
from radar.ui.panels.earthquake import EarthquakePanel
from radar.ui.panels.map import MapPanel
from radar.ui.panels.status_bar import StatusBar
from radar.ui.panels.weather import WeatherPanel
from radar.ui.viewport import (
    create_viewport,
    destroy_viewport,
    maximize_viewport,
    setup_viewport,
)

logger = logging.getLogger(__name__)


# Message types for thread-safe queue
class _EqUpdate:
    def __init__(self, events: list[EarthquakeEvent], diff: EarthquakeDiff) -> None:
        self.events = events
        self.diff = diff


class _WxUpdate:
    def __init__(self, data: WeatherData) -> None:
        self.data = data


class _ThemeReload:
    def __init__(self, name: str) -> None:
        self.name = name


class _LocationChange:
    def __init__(self, lat: float, lon: float, name: str) -> None:
        self.lat = lat
        self.lon = lon
        self.name = name


class _ConnectionStatus:
    def __init__(self, state: str) -> None:
        self.state = state


class RadarApp:
    """Main application class — ties everything together."""

    def __init__(self, config: RadarConfig) -> None:
        self._config = config
        self._queue: Queue[Any] = Queue()
        self._running = False
        self._theme: ThemeData | None = None
        self._active_theme_name: str = config.ui.theme

        # Audio engine
        self._audio = AudioEngine(
            sound_dir=SOUND_DIR,
            volume=config.audio.volume,
            enabled=config.audio.enabled,
        )

        # Felt warning state
        self._felt_warning_time: float = 0.0  # monotonic time when felt was triggered
        self._felt_warning_duration: float = float(config.audio.felt_warning_duration_s)
        self._felt_radius_km: float = config.audio.felt_radius_km
        self._eq_initial_load_done: bool = False  # Suppress audio on first bulk load

        # City Index
        logger.info("Loading city database...")
        self._city_index = CityIndex()
        self._city_index.load()

        self._force_eq_fetch = False

        # Data fetchers
        self._eq_fetcher = EarthquakeFetcher(
            feed_url=config.earthquake.feed_url,
            max_display=config.earthquake.max_display,
            mock_feed_file=config.debug.mock_feed_file,
        )
        self._wx_fetcher = WeatherFetcher(
            latitude=config.weather.latitude,
            longitude=config.weather.longitude,
            units=config.general.units,
        )

        # UI panels (created during build)
        self._eq_panel: EarthquakePanel | None = None
        self._wx_panel: WeatherPanel | None = None
        self._map_panel: MapPanel | None = None
        self._status_bar: StatusBar | None = None

        # Layout Manager
        self._layout = LayoutManager(
            on_resize=self._on_layout_resize,
            initial_split_x=config.ui.split_x,
            initial_split_y=config.ui.split_y,
        )

        # Theme watcher
        self._theme_watcher = ThemeWatcher(
            THEMES_DIR, self._on_theme_file_changed
        )
        
        # Theme Transition State
        self._old_theme: ThemeData | None = None
        self._target_theme: ThemeData | None = None
        self._theme_transition_start = 0.0
        self._theme_transition_duration = 0.0

        # Async loop
        self._async_loop: asyncio.AbstractEventLoop | None = None
        self._async_thread: threading.Thread | None = None
        self._stop_event: asyncio.Event | None = None

    # Theme handling
    def _load_initial_theme(self) -> ThemeData:
        """Load the configured theme, falling back to obsidian."""
        try:
            return load_theme(self._config.ui.theme)
        except FileNotFoundError:
            logger.warning(
                "Theme '%s' not found, falling back to obsidian", self._config.ui.theme
            )
            try:
                return load_theme("obsidian")
            except FileNotFoundError:
                # Emergency fallback: create minimal theme in memory
                logger.error("No themes found — using hardcoded fallback")
                return ThemeData(name="Fallback", colors={
                    "background": (13, 13, 13, 255),
                    "surface": (26, 26, 46, 255),
                    "primary": (0, 212, 255, 255),
                    "accent": (255, 107, 53, 255),
                    "text": (224, 224, 224, 255),
                    "text_dim": (102, 102, 128, 255),
                    "text_bright": (255, 255, 255, 255),
                    "success": (0, 255, 136, 255),
                    "warning": (255, 215, 0, 255),
                    "danger": (255, 51, 102, 255),
                    "border": (42, 42, 74, 255),
                    "header": (15, 15, 30, 255),
                    "row_even": (18, 18, 42, 255),
                    "row_odd": (22, 22, 58, 255),
                    "magnitude_low": (0, 255, 136, 255),
                    "magnitude_mid": (255, 215, 0, 255),
                    "magnitude_high": (255, 140, 0, 255),
                    "magnitude_severe": (255, 51, 102, 255),
                })

    def _on_theme_file_changed(self, theme_name: str) -> None:
        """Called by the file watcher when a theme file changes."""
        if theme_name == self._active_theme_name:
            self._queue.put(_ThemeReload(theme_name))

    def _apply_theme_switch(self, theme_name: str) -> None:
        """Switch to a different theme (called from UI thread)."""
        if theme_name == self._active_theme_name and self._target_theme is None:
            return

        try:
            new_theme = load_theme(theme_name)
            self._old_theme = self._theme
            self._target_theme = new_theme
            self._active_theme_name = theme_name
            self._theme_transition_start = time.monotonic()
            
            # Use whichever is slower so it's smooth
            duration_ms = max(self._old_theme.transition_ms if self._old_theme else 200, new_theme.transition_ms)
            self._theme_transition_duration = duration_ms / 1000.0

            logger.info("Starting theme transition to: %s (over %.2fs)", theme_name, self._theme_transition_duration)
        except Exception as e:
            logger.error("Failed to load theme '%s': %s", theme_name, e)

    def _update_theme_transition(self) -> None:
        """Process active theme interpolation."""
        if self._target_theme is None or self._old_theme is None:
            return

        from radar.themes.loader import transition_theme

        now = time.monotonic()
        elapsed = now - self._theme_transition_start
        progress = elapsed / self._theme_transition_duration if self._theme_transition_duration > 0 else 1.0

        if progress >= 1.0:
            # Transition complete
            self._theme = self._target_theme
            self._old_theme = None
            self._target_theme = None
            
            apply_theme(self._theme)
            
            # Final update
            if self._eq_panel: self._eq_panel.update_theme(self._theme)
            if self._wx_panel: self._wx_panel.update_theme(self._theme)
            if self._map_panel: self._map_panel.update_theme(self._theme)
            if self._status_bar: self._status_bar.update_theme(self._theme)
            
            logger.info("Theme transition complete.")
        else:
            # Interpolate
            interp_theme = transition_theme(self._old_theme, self._target_theme, progress)
            self._theme = interp_theme
            apply_theme(self._theme)
            
            # Soft-update components so dynamic draws (like Map vector colors) update
            # Some components caching colors might need full self._eq_panel.update_theme(),
            # but usually just changing DPG global theme is enough if they rely on it implicitly.
            # Panels that cache `self._theme.color()` directly need updates:
            if self._eq_panel: self._eq_panel.update_theme(self._theme, soft=True)
            if self._map_panel: self._map_panel.update_theme(self._theme)  # Force redraw
            if self._wx_panel: self._wx_panel.update_theme(self._theme, soft=True)
            if self._status_bar: self._status_bar.update_theme(self._theme, soft=True)

    # Async data fetching
    def _start_async_loop(self) -> None:
        """Start the async event loop in a background thread."""
        self._async_loop = asyncio.new_event_loop()
        self._stop_event = asyncio.Event()

        def _run():
            asyncio.set_event_loop(self._async_loop)
            try:
                self._async_loop.run_until_complete(self._fetch_loop())
            except Exception as e:
                logger.error("Async loop error: %s", e)
            finally:
                # Ensure loop is closed only after run_until_complete returns
                self._async_loop.close()

        self._async_thread = threading.Thread(target=_run, daemon=True, name="radar-async")
        self._async_thread.start()
        logger.info("Background async loop started")

    async def _fetch_loop(self) -> None:
        """Main async loop — periodically fetches earthquake and weather data."""
        eq_interval = self._config.earthquake.poll_interval
        wx_interval = self._config.weather.poll_interval

        last_eq = 0.0
        last_wx = 0.0

        try:
            while self._running:
                now = time.monotonic()

                # Earthquake fetch
                if now - last_eq >= eq_interval or self._force_eq_fetch:
                    self._force_eq_fetch = False
                    try:
                        events, diff = await self._eq_fetcher.fetch()
                        self._queue.put(_EqUpdate(events, diff))
                        last_eq = now
                    except Exception as e:
                        logger.error("Earthquake fetch loop error: %s", e)
                        self._queue.put(_ConnectionStatus("OFFLINE"))
                        last_eq = now

                # Weather fetch
                if now - last_wx >= wx_interval or self._wx_fetcher._last_fetch == 0.0:
                    try:
                        data = await self._wx_fetcher.fetch()
                        if data:
                            self._queue.put(_WxUpdate(data))
                        last_wx = now
                    except Exception as e:
                        logger.error("Weather fetch loop error: %s", e)

                # Interruption-aware sleep using Event
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=1.0)
                except (asyncio.TimeoutError, TimeoutError):
                    pass
        finally:
            logger.info("Closing data fetchers...")
            await self._eq_fetcher.close()
            await self._wx_fetcher.close()
            logger.debug("Fetchers closed")

    # UI building
    def _build_ui(self) -> None:
        """Create the main window layout with all panels."""
        assert self._theme is not None

        # Handle viewport resize events
        # Moved inside build_ui to ensure window exists

        # Custom theme for primary window to remove padding
        with dpg.theme() as layout_theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 0, 0)
                dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 0, 0)
                dpg.add_theme_style(dpg.mvStyleVar_ScrollbarSize, 0)  # Hide scrollbars visually

        with dpg.window(tag="primary_window", no_scrollbar=True, no_scroll_with_mouse=True):
            dpg.bind_item_theme(dpg.last_item(), layout_theme)
            # ── Panels ──
            
            # Earthquake Panel (Top Left)
            with dpg.child_window(tag="eq_panel_container", border=False):
                dpg.bind_item_theme(dpg.last_item(), layout_theme)
                self._eq_panel = EarthquakePanel(
                    self._theme,
                    highlight_threshold=self._config.earthquake.highlight_threshold,
                )
                # Set initial user location for distance sorting
                self._eq_panel.set_user_location(
                    self._config.weather.latitude,
                    self._config.weather.longitude
                )
                self._eq_panel.build(dpg.last_item())
                
                # Wire list-to-map selection + click sound
                def _on_eq_click(event_id: str) -> None:
                    if self._map_panel:
                        # Detect if this is a deselect (clicking the same one again)
                        is_deselect = (self._map_panel._selected_id == event_id)
                        self._map_panel.set_selection(event_id)
                        if is_deselect:
                            self._audio.play("unclick")
                        else:
                            self._audio.play("click")
                self._eq_panel.set_on_click(_on_eq_click)

            # Weather Panel (Top Right)
            with dpg.child_window(tag="wx_panel_container", border=False):
                dpg.bind_item_theme(dpg.last_item(), layout_theme)
                self._wx_panel = WeatherPanel(
                    self._theme,
                    city_index=self._city_index,
                    location_name=self._config.weather.location_name,
                    on_location_change=self._on_location_change,
                )
                self._wx_panel.build(dpg.last_item())

            # Map Panel (Bottom)
            with dpg.child_window(tag="map_panel_container", border=False):
                dpg.bind_item_theme(dpg.last_item(), layout_theme)
                
                def _on_map_hover(event_id: str) -> None:
                    if self._eq_panel:
                        self._eq_panel.highlight_event(event_id)
                
                def _on_map_click(event_id: str) -> None:
                    if self._eq_panel:
                        self._eq_panel.select_event(event_id)
                        
                self._map_panel = MapPanel(self._theme, on_hover=_on_map_hover, on_click=_on_map_click)
                self._map_panel.set_user_location(
                    self._config.weather.latitude,
                    self._config.weather.longitude
                )
                self._map_panel.build(dpg.last_item())

            # Splitters
            self._layout.draw_splitters("primary_window")

            # Status bar
            with dpg.child_window(tag="status_bar_container", border=False, no_scrollbar=True):
                dpg.bind_item_theme(dpg.last_item(), layout_theme)
                self._status_bar = StatusBar(
                    self._theme,
                    available_themes=get_available_themes(),
                    on_theme_change=lambda name: self._queue.put(_ThemeReload(name)),
                    on_retry=self._force_retry,
                )
                self._status_bar.build(dpg.last_item())

        # Setup handlers now that window exists
        self._layout.setup_handlers()

        # Initial layout update
        self._on_layout_resize()

        dpg.set_primary_window("primary_window", True)

    def _on_layout_resize(self) -> None:
        """Called when viewport resizes or splitters move."""
        # Update panel sizes based on layout manager
        eq_w, eq_h = self._layout.get_eq_size()
        wx_w, wx_h = self._layout.get_wx_size()
        map_w, map_h = self._layout.get_map_size()
        wx_x, wx_y = self._layout.get_wx_pos()
        map_x, map_y = self._layout.get_map_pos()
        
        total_w, total_h = self._layout.get_total_size()

        dpg.configure_item("eq_panel_container", width=eq_w, height=eq_h, pos=(0, 0))
        dpg.configure_item("wx_panel_container", width=wx_w, height=wx_h, pos=(wx_x, wx_y))
        dpg.configure_item("map_panel_container", width=map_w, height=map_h, pos=(map_x, map_y))
        
        # Position status bar at the very bottom
        if dpg.does_item_exist("status_bar_container"):
            dpg.configure_item("status_bar_container", width=total_w, height=32, pos=(0, total_h - 32))

        # Notify map and weather panel to redraw (they need explicit resize)
        if self._map_panel:
            self._map_panel.resize(map_w, map_h)
            
        if self._wx_panel:
            self._wx_panel.resize(wx_w, wx_h)

    def _on_location_change(self, lat: float, lon: float, name: str) -> None:
        """Callback from weather panel when city is selected."""
        self._queue.put(_LocationChange(lat, lon, name))

    # Frame update callback
    def _frame_update(self) -> None:
        """Called every frame — processes queued updates and animations."""
        # Process all queued messages
        while True:
            try:
                msg = self._queue.get_nowait()
            except Empty:
                break

            if isinstance(msg, _EqUpdate):
                new_ids = [e.id for e in msg.diff.added] if msg.diff.added else []
                updated_ids = [e.id for e in msg.diff.updated] if hasattr(msg.diff, 'updated') and msg.diff.updated else []
                all_new = new_ids + updated_ids
                if self._eq_panel:
                    self._eq_panel.update(msg.events, all_new)
                if self._map_panel:
                    self._map_panel.update(msg.events, all_new)
                if self._status_bar:
                    now = datetime.now(timezone.utc).strftime("%H:%M:%S")
                    self._status_bar.set_last_earthquake_update(now)
                    self._status_bar.set_status("ONLINE")

                # Audio alerts for new earthquakes (skip the initial bulk load)
                if msg.diff.added and self._eq_initial_load_done:
                    strongest = max(msg.diff.added, key=lambda e: e.magnitude)
                    self._audio.play_for_magnitude(strongest.magnitude)

                    # Check if any new quake is "felt" at the station
                    if self._felt_radius_km > 0 and self._eq_panel:
                        user_lat = self._config.weather.latitude
                        user_lon = self._config.weather.longitude
                        for ev in msg.diff.added:
                            dist = self._eq_panel._haversine(
                                user_lat, user_lon, ev.latitude, ev.longitude
                            )
                            if dist <= self._felt_radius_km:
                                self._audio.play_felt()
                                self._felt_warning_time = time.monotonic()
                                logger.info(
                                    "FELT: M%.1f at %.0f km from station",
                                    ev.magnitude, dist,
                                )
                                break  # One alert is enough

                # Play update tick if there are updates
                if hasattr(msg.diff, 'updated') and msg.diff.updated and self._eq_initial_load_done:
                    self._audio.play("update")

                # Mark initial load as done after first update
                if not self._eq_initial_load_done:
                    self._eq_initial_load_done = True

            elif isinstance(msg, _WxUpdate):
                if self._wx_panel:
                    self._wx_panel.update(msg.data)

            elif isinstance(msg, _ThemeReload):
                self._audio.play("click")
                self._apply_theme_switch(msg.name)

            elif isinstance(msg, _ConnectionStatus):
                if self._status_bar:
                    self._status_bar.set_status(msg.state)

            elif isinstance(msg, _LocationChange):
                logger.info("Changing location to: %s", msg.name)
                # Update fetcher target
                self._wx_fetcher.set_location(msg.lat, msg.lon)
                # Update config in memory (optional: save to file?)
                self._config.weather.latitude = msg.lat
                self._config.weather.longitude = msg.lon
                self._config.weather.location_name = msg.name
                
                # Update Earthquake Panel location
                if self._eq_panel:
                    self._eq_panel.set_user_location(msg.lat, msg.lon)

                # Update Map Panel location
                if self._map_panel:
                    self._map_panel.set_user_location(msg.lat, msg.lon)

        # Process animations
        if self._wx_panel:
            self._wx_panel._frame_tick()

        # Process theme transitions
        self._update_theme_transition()

        # Update animations
        if self._eq_panel:
            self._eq_panel.update_highlights()
            
        if self._map_panel:
            # Drive the felt warning blink on the map header
            felt_active = False
            if self._felt_warning_time > 0:
                elapsed = time.monotonic() - self._felt_warning_time
                if elapsed < self._felt_warning_duration:
                    felt_active = True
                else:
                    self._felt_warning_time = 0.0
            self._map_panel.set_felt_warning(felt_active)
            self._map_panel.update_animations()

        # Update clock and FPS
        if self._status_bar:
            self._status_bar.update_clock()
            self._status_bar.update_fps(dpg.get_frame_rate())

    def _force_retry(self) -> None:
        # Prevent API throttling by spamming manual fetch
        if self._status_bar and "status" in self._status_bar._tags:
            current_status = str(dpg.get_value(self._status_bar._tags["status"]))
            if "CONNECTING" in current_status:
                return
                
            now = time.monotonic()
            if "ONLINE" in current_status:
                if hasattr(self, "_last_manual_retry") and now - self._last_manual_retry < 45.0:
                    return
                self._last_manual_retry = now

        self._force_eq_fetch = True
        if self._status_bar:
            self._status_bar.set_status("CONNECTING")

    # Public interface
    def run(self) -> None:
        """Launch the application."""
        logger.info("Starting Radar...")

        # 1. Create viewport
        create_viewport(self._config)

        # 2. Load and apply theme
        self._theme = self._load_initial_theme()
        apply_theme(self._theme)

        # 3. Build UI
        self._build_ui()

        # 4. Finalize viewport
        setup_viewport()

        if self._config.ui.start_maximized:
            maximize_viewport()

        # 5. Start background data fetching
        self._running = True
        self._audio.start()
        self._start_async_loop()

        # 6. Start theme hot-reload watcher
        self._theme_watcher.start()

        # 7. Main render loop
        logger.info("Radar is running — Ctrl+C to stop")
        
        target_fps = 60
        frame_time = 1.0 / target_fps
        
        try:
            while dpg.is_dearpygui_running():
                start_time = time.monotonic()
                
                self._frame_update()
                dpg.render_dearpygui_frame()
                
                # FPS Limiter
                elapsed = time.monotonic() - start_time
                if elapsed < frame_time:
                    time.sleep(frame_time - elapsed)
        except KeyboardInterrupt:
            logger.info("Shutdown requested")
        finally:
            self._shutdown()

    def _shutdown(self) -> None:
        """Clean shutdown of all subsystems."""
        logger.info("Shutting down...")
        self._running = False

        # Stop audio
        self._audio.stop()

        # Stop theme watcher
        self._theme_watcher.stop()

        # Stop async loop gracefully via event
        if self._async_loop and self._stop_event:
            self._async_loop.call_soon_threadsafe(self._stop_event.set)

        if self._async_thread:
            self._async_thread.join(timeout=3.0)

        # Destroy viewport
        destroy_viewport()
        logger.info("Radar stopped")

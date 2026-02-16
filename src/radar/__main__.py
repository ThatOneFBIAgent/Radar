"""
Entry point for Radar — python -m radar
"""

from __future__ import annotations

import sys


def main() -> None:
    """Launch the Radar application."""
    from radar.config import load_config
    from radar.logging_setup import setup_logging

    # Load config first
    config = load_config()

    # Setup logging with configured level
    setup_logging(config.general.log_level)

    # Import app after logging is configured
    from radar.app import RadarApp

    app = RadarApp(config)
    app.run()


if __name__ == "__main__":
    main()

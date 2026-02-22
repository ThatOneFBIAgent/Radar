"""
Entry point for Radar — python -m radar
"""

from __future__ import annotations

import sys
import argparse
import traceback
from datetime import datetime


def main() -> None:
    """Launch the Radar application."""
    parser = argparse.ArgumentParser(description="RADAR - Seismic & Weather Monitor")
    parser.add_argument("--quiet", action="store_true", help="Disable console logging")
    parser.add_argument("--debug", action="store_true", help="Force DEBUG log level")
    args = parser.parse_args()

    from radar.config import load_config, LOG_DIR
    from radar.logging_setup import setup_logging

    # Load config first
    config = load_config()

    # Override log level if flags are set
    log_level = config.general.log_level
    log_file = None
    
    if args.quiet:
        log_level = "INFO" # Keep info level but send to file
        log_file = LOG_DIR / "radar.log"
    elif args.debug:
        log_level = "DEBUG"

    # If frozen and not debug, also log to file for troubleshooting
    if getattr(sys, "frozen", False) and not args.debug:
        log_file = LOG_DIR / "radar.log"

    # Setup logging
    setup_logging(log_level, log_file=log_file)

    # Import app after logging is configured
    from radar.app import RadarApp

    try:
        app = RadarApp(config)
        app.run()
    except Exception:
        if getattr(sys, "frozen", False):
            # Log to a file if we're in frozen/windowed mode
            crash_log = LOG_DIR / "radar_crash.log"
            with open(crash_log, "w", encoding="utf-8") as f:
                f.write("="*50 + "\n")
                f.write(f"RADAR CRITICAL ERROR - {datetime.now()}\n")
                f.write("="*50 + "\n\n")
                traceback.print_exc(file=f)
                f.write("\n" + "="*50 + "\n")
            
            # Since there's no console, we can't use input(). 
            # The app just exits, but the log remains.
        else:
            raise


if __name__ == "__main__":
    main()

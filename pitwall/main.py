"""
main.py - PitWall Application Entry Point

Supports:
1. 3D Glassmorphism UI Mode (default):
   Exports HTML to a cross-platform temp folder, launches it in the browser,
   and automatically purges the temp directory upon exit.
2. Terminal-Only Mode (--terminal / -t):
   Outputs all transmissions cleanly and neatly directly into the console,
   exports the HTML snapshot to the cross-platform temp folder, and
   purges the temp directory upon exit.
"""

from __future__ import annotations

import argparse
import atexit
import os
import shutil
import sys
import tempfile
from typing import Any, List

# Ensure local module directory is in sys.path for cross-directory invocation
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if _CURRENT_DIR not in sys.path:
    sys.path.insert(0, _CURRENT_DIR)

try:
    from report.terminal import render_dashboard, render_terminal
except ImportError:
    from pitwall.report.terminal import render_dashboard, render_terminal

try:
    from providers.x_provider import XProvider
except (ImportError, ModuleNotFoundError):
    try:
        from pitwall.providers.x_provider import XProvider
    except (ImportError, ModuleNotFoundError):
        XProvider = None


MOCK_POSTS = [
    {
        "text": "POLE POSITION IN MONZA! 🔴 An astonishing lap at the Temple of Speed sets up a thrilling Grand Prix weekend! #F1 #ItalianGP @ScuderiaFerrari",
        "timestamp": "2m",
        "url": "https://x.com/F1/status/123456789",
        "image_url": [
            "https://picsum.photos/seed/monza1/800/600",
            "https://picsum.photos/seed/monza2/800/600",
        ],
    },
    {
        "text": "Full telemetry breakdown from Sector 2: Apex speeds are 12 km/h higher with the new low-drag rear wing configuration. Pit strategy will be crucial tomorrow under tire degradation.",
        "timestamp": "14m",
        "url": "https://x.com/F1/status/123456790",
        "image_url": [
            "https://picsum.photos/seed/telemetry/900/500",
            "https://picsum.photos/seed/paddock/800/600",
            "https://picsum.photos/seed/tires/800/600",
            "https://picsum.photos/seed/pitstop/800/600",
        ],
    },
    {
        "text": "Weather radar indicates a 40% chance of rain before lights out. Track temperature currently sitting at 38°C. #F1Telemetry",
        "timestamp": "1h",
        "url": "https://x.com/F1/status/123456791",
        "image_url": [],
    },
    {
        "text": "Championship standings update ahead of lights out: 5 points separate the top two contenders as we enter the European leg! 🏆",
        "timestamp": "3h",
        "url": "https://x.com/F1/status/123456792",
        "image_url": ["https://picsum.photos/seed/standings/800/600"],
    },
    {
        "text": "Green flag in 30 minutes. All systems nominal on the pit wall. Ready for radio check. 📻",
        "timestamp": "5h",
        "url": "https://x.com/F1/status/123456793",
        "image_url": [],
    },
]


def _cleanup_temp_dir(path: str) -> None:
    """Safely cleans up temporary files and folders across all operating systems."""
    if path and os.path.exists(path):
        try:
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
            else:
                os.remove(path)
        except Exception:
            pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="PitWall - Formula 1 Telemetry and Social Feed Dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--terminal",
        "-t",
        action="store_true",
        help="Display all posts neatly in the terminal rather than opening the browser UI",
    )
    parser.add_argument(
        "--count",
        "-n",
        type=int,
        default=5,
        help="Number of posts to retrieve (default: 5)",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use built-in mock Formula 1 posts (useful for offline testing or verification)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Multiplatform temporary directory creation
    temp_dir = tempfile.mkdtemp(prefix="pitwall_")
    html_output_path = os.path.join(temp_dir, "dashboard.html")

    # Register automatic cleanup hook on process exit
    atexit.register(_cleanup_temp_dir, temp_dir)

    provider = None
    posts: List[Any] = []

    try:
        if args.mock or XProvider is None:
            if not args.mock and XProvider is None:
                print("[PitWall Notice] XProvider dependencies not installed. Using Formula 1 sample feed.")
            posts = MOCK_POSTS[: args.count]
        else:
            try:
                provider = XProvider()
                provider.connect()

                for iter in range(args.count):
                    posts.append(provider.find_posts(iter))
            except Exception as e:
                print(f"[PitWall Warning] Could not connect to live provider: {e}")
                print("[PitWall Notice] Falling back to sample telemetry data...")
                posts = MOCK_POSTS[: args.count]

        # Export HTML file to multiplatform temp folder
        is_terminal_mode = args.terminal
        render_dashboard(
            posts,
            output_path=html_output_path,
            open_browser=not is_terminal_mode,
        )

        if is_terminal_mode:
            print(f"[PitWall] HTML report exported to temp: {html_output_path}")
            print("[PitWall] Rendering telemetry in terminal mode:\n")
            render_terminal(posts)
        else:
            print(f"[PitWall] 3D Glassmorphism dashboard opened from temp: {html_output_path}")

        try:
            input("\nPress Enter to close PitWall and clean up temporary files...")
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")

    finally:
        # Guarantee cleanup when user exits
        if provider:
            try:
                provider.close()
            except Exception:
                pass

        _cleanup_temp_dir(temp_dir)
        print("[PitWall] Cleaned up temporary files. PitWall shut down.")


if __name__ == "__main__":
    main()
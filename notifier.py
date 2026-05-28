"""
macOS desktop notification via osascript. No extra dependencies required.
"""

import subprocess


def notify(title: str, message: str) -> None:
    script = f'display notification "{message}" with title "{title}" sound name "Glass"'
    try:
        subprocess.run(["osascript", "-e", script], check=True)
    except Exception as e:
        print(f"Notification failed: {e}")

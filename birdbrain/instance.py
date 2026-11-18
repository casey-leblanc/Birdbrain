"""One Birdbrain at a time (two would fight over the browser profile).

The first copy to start holds a named lock for as long as it runs. A copy started while it's held hands over to the
running one (asks it to show its window) and leaves. The lock is asked for once per process: asking Windows for it a
second time would find our own, and look like another copy.
"""
from __future__ import annotations

import sys

import system


def already_running(name: str | None = None) -> bool:
    """True if another copy of Birdbrain holds the lock (system.py). However often it's asked, the answer is the first one."""
    return system.another_copy_holds(name) if name else system.another_copy_holds()


def start_or_hand_over(argv: list[str], running=already_running, show=lambda: False) -> str:
    """What a copy that has just started should do: "start" (it's the only one); "leave" (another is running and
    has been asked to show its window, or it was started with --quiet, which wants nothing shown); or "tell"
    (another is running but couldn't be reached: say so)."""
    if not running():
        return "start"
    if "--quiet" in argv:
        return "leave"
    return "leave" if show() else "tell"

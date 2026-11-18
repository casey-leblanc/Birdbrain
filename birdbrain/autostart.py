"""Start with the computer, so reminders arrive without opening Birdbrain first.

Notifications only come while Birdbrain is running. A packaged copy can ask to be started when you sign in. On
Windows that is one value under your own account's Run key (HKEY_CURRENT_USER, so no administrator rights, and
nothing for other users of the PC); on a Mac, a LaunchAgent of your own (system.py has both). It starts with
--background: in the tray or menu bar, window closed.

The welcome page offers it, already ticked; Settings › Notifications turns it on or off afterwards. A copy run from
source has no program of its own to start, so there the choice isn't offered.
"""
from __future__ import annotations

import logging
import sys

import system

log = logging.getLogger(__name__)

NAME = "Birdbrain"


def available() -> bool:
    return system.autostart_available()


def command(program: str | None = None) -> str:
    return f'"{program or sys.executable}" --background'


def _read(name: str) -> str | None:
    return system.autostart_read(name)


def _write(name: str, value: str | None) -> None:
    system.autostart_write(name, value)


def is_on(name: str = NAME, program: str | None = None) -> bool:
    """Whether this copy is set to start with Windows (a value left by a copy that has since moved doesn't count)."""
    try:
        return _read(name) == command(program)
    except OSError:
        log.exception("Couldn't read the start-up setting")
        return False


def turn(on: bool, name: str = NAME, program: str | None = None) -> bool:
    """Turn it on or off. Says whether it is now as asked."""
    try:
        _write(name, command(program) if on else None)
    except OSError:
        log.exception("Couldn't change the start-up setting")
        return False
    return is_on(name, program) == on


def view() -> dict:
    return {"available": available(), "on": available() and is_on()}

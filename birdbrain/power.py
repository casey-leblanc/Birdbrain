"""Sleep and wake: scanning on time when the PC has been asleep, and staying awake while a scan runs.

- wait(): waits for the next scan by the clock on the wall, so time spent asleep counts. A PC that slept through its
  scan time scans as soon as it wakes (once the network is back), instead of an hour later.
- awake(): asks Windows not to go to sleep while a scan runs.
"""
from __future__ import annotations

import logging
import socket
import sys
import time
from threading import Event
from urllib.parse import urlparse

import system

log = logging.getLogger(__name__)

SLICE = 30          # seconds between looks at the clock
JUMP = 120          # the clock moving this much further than we waited means the PC was asleep
STALE = 15 * 60     # after a wake, scan if the last one is at least this old


def wait(wake: Event, seconds: float, stop: Event, clock=time.time) -> str:
    """Wait for the next scan: until `wake` is set ("asked"), `seconds` have passed on the wall clock ("due"), or
    the PC has come back from sleep with the last scan gone stale ("woke"). `stop` ends it ("stop")."""
    began = last = clock()
    while True:
        if wake.wait(SLICE):
            return "asked"
        if stop.is_set():
            return "stop"
        now = clock()
        slept = now - last - SLICE > JUMP
        last = now
        if now - began >= seconds:
            return "woke" if slept else "due"
        if slept and now - began >= STALE:
            return "woke"


def online(address: str, tries: int = 12, pause: float = 10, connect=socket.create_connection) -> bool:
    """After a wake the network takes a moment: wait (up to two minutes) until the site answers."""
    host = urlparse(address).hostname or address
    for n in range(tries):
        try:
            connect((host, 443), timeout=5).close()
            return True
        except OSError:
            if n < tries - 1:
                time.sleep(pause)
    return False


def awake():
    """Keep the computer from going to sleep until the block ends (the display can still turn off): system.py."""
    return system.keep_awake()

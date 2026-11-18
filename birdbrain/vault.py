"""A secret kept by the system, not in Birdbrain's settings file.

The only one is the Telegram bot's token (Settings › Advanced › Telegram): what a stranger could use if they got
hold of the settings file (a backup, a synced folder, a screenshot). On Windows it goes in Credential Manager,
encrypted for your Windows account; you can see and remove it under Control Panel › Credential Manager › Windows
Credentials, as "Birdbrain/telegram_token". On a Mac it goes in your login keychain, as "Birdbrain".

Where the system has no such place, nothing is kept and Telegram can't be turned on: the token never goes in a file.
"""
from __future__ import annotations

import logging
import os

import system

log = logging.getLogger(__name__)

SECRETS = ("telegram_token",)
PREFIX = "Birdbrain/"


def available() -> bool:
    """Where the system has a credential store (system.py), unless switched off (the tests never touch real keys)."""
    return system.secrets_available() and not os.environ.get("BIRDBRAIN_NO_VAULT")


def get(name: str, prefix: str = PREFIX) -> str | None:
    """The stored value, "" if there's none, or None if the system's store couldn't be read."""
    return system.secret_get(name, prefix)


def put(name: str, value: str, prefix: str = PREFIX) -> bool:
    """Store the value (or remove it, for ""), and read it back to be sure. False if it isn't safely there."""
    if not system.secret_put(name, value, prefix):
        return False
    return not value or get(name, prefix) == value

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
import sys

log = logging.getLogger(__name__)

SECRETS = ("telegram_token",)
PREFIX = "Birdbrain/"
_GENERIC, _LOCAL_MACHINE, _NOT_FOUND = 1, 2, 1168
_api = None


def available() -> bool:
    """On Windows and macOS, unless switched off (the tests and the self-test never touch your real keys)."""
    return sys.platform in ("win32", "darwin") and not os.environ.get("BIRDBRAIN_NO_VAULT")


def _load():
    global _api
    if _api is None:
        import ctypes
        from ctypes import wintypes

        class Credential(ctypes.Structure):
            _fields_ = [("Flags", wintypes.DWORD), ("Type", wintypes.DWORD), ("TargetName", wintypes.LPWSTR),
                        ("Comment", wintypes.LPWSTR), ("LastWritten", wintypes.FILETIME),
                        ("CredentialBlobSize", wintypes.DWORD), ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
                        ("Persist", wintypes.DWORD), ("AttributeCount", wintypes.DWORD), ("Attributes", ctypes.c_void_p),
                        ("TargetAlias", wintypes.LPWSTR), ("UserName", wintypes.LPWSTR)]

        lib = ctypes.WinDLL("advapi32", use_last_error=True)
        lib.CredWriteW.argtypes = [ctypes.POINTER(Credential), wintypes.DWORD]
        lib.CredWriteW.restype = wintypes.BOOL
        lib.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  ctypes.POINTER(ctypes.POINTER(Credential))]
        lib.CredReadW.restype = wintypes.BOOL
        lib.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        lib.CredDeleteW.restype = wintypes.BOOL
        lib.CredFree.argtypes = [ctypes.c_void_p]
        lib.CredFree.restype = None
        _api = (ctypes, lib, Credential)
    return _api


def _keychain(*args: str, secret: str | None = None) -> tuple[int, str]:
    """Run macOS's `security` tool; (exit code, what it printed)."""
    import subprocess
    done = subprocess.run(["/usr/bin/security", *args], capture_output=True, text=True, timeout=20)
    return done.returncode, done.stdout.strip()


def get(name: str, prefix: str = PREFIX) -> str | None:
    """The stored value, "" if there's none, or None if the system's store couldn't be read."""
    if sys.platform == "darwin":
        try:
            code, out = _keychain("find-generic-password", "-s", prefix.rstrip("/"), "-a", name, "-w")
            return out if code == 0 else "" if code == 44 else None   # 44: no such item
        except Exception:
            log.exception("Couldn't read %s from the keychain", name)
            return None
    try:
        ctypes, lib, Credential = _load()
        p = ctypes.POINTER(Credential)()
        if not lib.CredReadW(prefix + name, _GENERIC, 0, ctypes.byref(p)):
            return "" if ctypes.get_last_error() == _NOT_FOUND else None
        try:
            c = p.contents
            return ctypes.string_at(c.CredentialBlob, c.CredentialBlobSize).decode("utf-8")
        finally:
            lib.CredFree(p)
    except Exception:
        log.exception("Couldn't read %s from Credential Manager", name)
        return None


def put(name: str, value: str, prefix: str = PREFIX) -> bool:
    """Store the value (or remove it, for ""), and read it back to be sure. False if it isn't safely there."""
    if sys.platform == "darwin":
        try:
            if not value:
                return _keychain("delete-generic-password", "-s", prefix.rstrip("/"), "-a", name)[0] in (0, 44)
            code, _ = _keychain("add-generic-password", "-U", "-s", prefix.rstrip("/"), "-a", name, "-w", value,
                                "-j", "Kept by Birdbrain")
            return code == 0 and get(name, prefix) == value
        except Exception:
            log.exception("Couldn't write %s to the keychain", name)
            return False
    try:
        ctypes, lib, Credential = _load()
        if not value:
            ok = lib.CredDeleteW(prefix + name, _GENERIC, 0) or ctypes.get_last_error() == _NOT_FOUND
            return bool(ok)
        blob = value.encode("utf-8")
        buf = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
        cred = Credential(Type=_GENERIC, TargetName=prefix + name, Comment="Kept by Birdbrain",
                          CredentialBlobSize=len(blob), CredentialBlob=ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)),
                          Persist=_LOCAL_MACHINE, UserName="Birdbrain")
        if not lib.CredWriteW(ctypes.byref(cred), 0):
            log.warning("Credential Manager wouldn't take %s (error %s)", name, ctypes.get_last_error())
            return False
        return get(name, prefix) == value
    except Exception:
        log.exception("Couldn't write %s to Credential Manager", name)
        return False

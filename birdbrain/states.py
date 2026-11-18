"""The states in between: when a scan didn't go as it should, one line that says what is going on and what to do.

    You're offline. Your list is as it was; Birdbrain scans again as soon as you're back online.
    Updated 10:32 AM. Couldn't reach Moodle at moodle.lsu.edu: check your connection, or the address in Settings › Advanced.
    Updated 10:32 AM. Moodle couldn't be read: its page may have changed. Your list is as it was; check for updates in the menu.
    Updated 10:32 AM. Moodle needs sign-in.

A scan that fails is one of three things. The site wants signing in to again (the list page puts a Sign in card at
the top). The site couldn't be reached: the connection is down, or the address is wrong. Or the site answered but
Birdbrain couldn't make sense of the page, which usually means the site has changed and a newer Birdbrain is needed.
When every site was out of reach at once, that is the computer being offline, and it is said once, not per site.

(The other states in between are the list's own: nothing due today, everything done, the first scan still running.
report.py draws those.)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

# What Chromium says when a site can't be reached at all.
OUT_OF_REACH = re.compile(r"ERR_INTERNET_DISCONNECTED|ERR_NETWORK_CHANGED|ERR_NAME_NOT_RESOLVED|ERR_ADDRESS_UNREACHABLE|"
                          r"ERR_CONNECTION_REFUSED|ERR_CONNECTION_RESET|ERR_CONNECTION_TIMED_OUT|ERR_CONNECTION_CLOSED|"
                          r"ERR_TIMED_OUT|ERR_PROXY_CONNECTION_FAILED|ERR_TUNNEL_CONNECTION_FAILED|ERR_CERT_|ERR_SSL_PROTOCOL|"
                          r"ERR_INVALID_URL|ERR_TOO_MANY_REDIRECTS")
DIDNT_FINISH = "The last scan didn't finish. Birdbrain will try again; if it keeps happening, use Report a problem in the menu."
OFFLINE = "You're offline. Your list is as it was; Birdbrain scans again as soon as you're back online."


@dataclass
class Problem:
    site: str          # "Moodle"
    kind: str          # "sign-in" | "unreachable" | "changed"
    address: str = ""  # where the site is, for "unreachable"

    @property
    def line(self) -> str:
        if self.kind == "sign-in":
            return f"{self.site} needs sign-in"
        if self.kind == "unreachable":
            host = urlparse(self.address).netloc or self.address
            at = f" at {host}" if host else ""
            return f"Couldn't reach {self.site}{at}: check your connection, or the address in Settings › Advanced"
        return (f"{self.site} couldn't be read: its page may have changed. Your list is as it was; "
                "check for updates in the menu")


def problem(site: str, error: Exception, address: str = "") -> Problem:
    """What kind of trouble a failed scan of one site was."""
    return Problem(site, "unreachable" if OUT_OF_REACH.search(str(error)) else "changed", address)


def offline(problems: list[Problem], sites: int) -> bool:
    """Every site was out of reach at once: that's the computer, not the sites."""
    return sites > 0 and len(problems) == sites and all(p.kind == "unreachable" for p in problems)


def status(when: str, problems: list[Problem], sites: int) -> str:
    """The status line after a scan that finished at `when` ("10:32 AM")."""
    if offline(problems, sites):
        return OFFLINE
    if not problems:
        return f"Updated {when}."
    return f"Updated {when}. " + "; ".join(p.line for p in problems) + "."

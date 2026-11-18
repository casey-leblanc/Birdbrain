"""Birdbrain's own window: appwindow_win.py on Windows (WebView2, with Birdbrain's own title bar), appwindow_mac.py
on a Mac (an ordinary Mac window, the standard menu, and a Dock icon that brings the window back).

Both have the same things in them: check(), available(), AppWindow, QuickWindow, and QUICK_WINDOW, which says whether
the small always-on-top quick write window exists on this system.
"""
import sys

if sys.platform == "darwin":
    import appwindow_mac as _impl
    from appwindow_mac import *   # noqa: F401,F403
else:
    import appwindow_win as _impl
    from appwindow_win import *   # noqa: F401,F403


def why_not() -> str:
    """Why the window can't be made here, in plain words, once available() has said no."""
    return _impl.problem

"""Everything that depends on the computer Birdbrain runs on, in one place.

There are two halves with the same names in each: system_win.py and system_mac.py. This module is whichever one
fits (on anything that isn't a Mac, the Windows half, whose pure parts are what the tests use on Linux). The rest of
Birdbrain asks here and nowhere else:

    where things are kept       data_dir, update_dir, browsers_dir, app_root, program_in
    one running copy            another_copy_holds, listen_for_show, show_running_copy
    the credential store        secrets_available, secret_get, secret_put
    start when you sign in      autostart_available, autostart_read, autostart_write
    during a scan               keep_awake
    telling you                 notify, hear_clicks (NOTIFY_CLICKS), play
    your files                  open_file, reveal
    signing in                  signin_channel (SIGNIN_BROWSER)
    updating                    ASSET, UNPACKED, unpack, update_blocked, swap_script, run_swap
    words                       NAME, MOD ("Ctrl" or "Cmd"), PROGRAM, TRAY
    what isn't there            HOTKEY, NOTIFY_CLICKS: False where this system can't do it yet, and the page hides it

A feature a system can't have yet is switched off by its half, so the rest of the app hides it instead of breaking.
"""
import sys

if sys.platform == "darwin":
    from system_mac import *       # noqa: F401,F403
    import system_mac as half
else:
    from system_win import *       # noqa: F401,F403
    import system_win as half

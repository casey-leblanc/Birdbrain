"""Birdbrain's own window on a Mac.

An ordinary Mac window: the system's own title bar and traffic lights, not the one Birdbrain draws for itself on
Windows. Closing it hides it; Birdbrain stays in the menu bar and the Dock, and clicking the Dock icon brings the
window back. The standard menu is there, with Settings… (Cmd+,) added and Quit made to really quit (the window's
"close means hide" would otherwise stop it).

The small always-on-top quick write window isn't on the Mac yet (QUICK_WINDOW): quick write opens in the main window.

None of this can be run anywhere but a Mac, so each extra (the menu, the Dock) is put on separately and logged:
if one can't be done, the window still works and the log says which.
"""
from __future__ import annotations

import logging
import threading

log = logging.getLogger(__name__)

problem = ""            # why the window can't be made here, in plain words, once check() has failed
QUICK_WINDOW = False    # no small quick write window on the Mac yet


def check() -> str:
    """Raises if the window can't be made here; otherwise says what it will use."""
    import webview   # noqa: F401
    from webview.platforms import cocoa   # noqa: F401  (loads the Mac's own web view)
    return "the Mac's own web view (WebKit)"


def available() -> bool:
    global problem
    try:
        check()
        return True
    except Exception:
        log.exception("No app window available; the list will open in the browser")
        problem = "Birdbrain's own window couldn't start, so your list opens in your browser. The log says why."
        return False


class QuickWindow:
    """Not on the Mac yet. Kept so the rest of the app has one shape on both systems."""

    def __init__(self, url: str):
        self.url = url

    def show(self) -> None:
        raise RuntimeError("no quick write window on the Mac")

    def hide(self) -> None:
        pass


def _on_main(fn) -> None:
    """Run something on the Mac's main thread, where everything that touches the window or the menu has to be."""
    from PyObjCTools import AppHelper
    AppHelper.callAfter(fn)


class AppWindow:
    def __init__(self, url: str, icon_path: str | None = None):
        import webview
        self.quitting = False
        self.ready = threading.Event()
        self.on_settings = lambda: None    # the menu's Settings…
        self.on_quit = lambda: None        # the menu's Quit
        self._target = None
        self.window = webview.create_window("Birdbrain", url, width=1320, height=900, min_size=(420, 560), hidden=True,
                                            background_color="#20242C", text_select=True)
        self.window.events.closing += self._on_closing

    def _on_closing(self) -> bool:
        if self.quitting:
            return True
        self.window.hide()   # keep running in the menu bar and the Dock
        return False         # cancels the close

    # --- the Dock icon, and the standard menu ------------------------------------------------------------------------
    def _hear_dock(self) -> None:
        """Clicking the Dock icon (or opening the app again) brings the window back."""
        try:
            import objc
            from webview.platforms import cocoa
            owner = self

            def applicationShouldHandleReopen_hasVisibleWindows_(self, app, visible):
                log.info("Opened again (the Dock icon, or the app itself): showing the window")
                threading.Thread(target=owner.show, daemon=True, name="dock-reopen").start()
                return True
            yes = objc._C_NSBOOL
            objc.classAddMethods(cocoa.BrowserView.AppDelegate, [objc.selector(
                applicationShouldHandleReopen_hasVisibleWindows_, selector=b"applicationShouldHandleReopen:hasVisibleWindows:",
                signature=yes + b"@:@" + yes)])
            log.info("Mac: the Dock icon reopens the window")
        except Exception:
            log.exception("Mac: couldn't listen for the Dock icon; the menu bar icon still opens the window")

    def _menu(self) -> None:
        """Settings… (Cmd+,) in the app's own menu, and Quit that quits. Run on the main thread."""
        try:
            import AppKit
            import Foundation
            owner = self

            class BirdbrainMenu(Foundation.NSObject):
                def birdbrainSettings_(self, sender):
                    threading.Thread(target=owner.on_settings, daemon=True, name="menu-settings").start()

                def birdbrainQuit_(self, sender):
                    threading.Thread(target=owner.on_quit, daemon=True, name="menu-quit").start()

            self._target = BirdbrainMenu.alloc().init()
            bar = AppKit.NSApp.mainMenu()
            menu = bar.itemAtIndex_(0).submenu()
            for n in range(menu.numberOfItems()):
                item = menu.itemAtIndex_(n)
                if item.keyEquivalent() == "q":            # Quit: ours, so "close means hide" can't stop it
                    item.setTarget_(self._target)
                    item.setAction_("birdbrainQuit:")
                    item.setTitle_("Quit Birdbrain")
            settings = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Settings…", "birdbrainSettings:", ",")
            settings.setTarget_(self._target)
            menu.insertItem_atIndex_(AppKit.NSMenuItem.separatorItem(), 1)
            menu.insertItem_atIndex_(settings, 2)
            titles = [str(menu.itemAtIndex_(n).title()) for n in range(menu.numberOfItems()) if menu.itemAtIndex_(n).title()]
            log.info("Mac menu: %s", ", ".join(titles))
        except Exception:
            log.exception("Mac: couldn't set up the menu; the window and the menu bar icon still work")

    def run(self, show: bool) -> None:
        """Run the window's event loop on this (the main) thread until quit()."""
        import webview
        self._hear_dock()

        def started():
            self.ready.set()
            _on_main(self._menu)
            if show:
                self.show()
        webview.start(started, private_mode=True)

    def show(self) -> None:
        """Bring the window up (from any thread)."""
        if not self.ready.wait(20):
            return
        self.window.show()
        try:
            import AppKit
            _on_main(lambda: AppKit.NSApp.activateIgnoringOtherApps_(True))
        except Exception:
            log.exception("Mac: couldn't bring Birdbrain to the front")

    def command(self, what: str) -> None:
        """Ask the page to do one of its commands (commands.py): the menu's Settings… opens Settings."""
        self.show()
        try:
            self.window.evaluate_js(f"window.birdbrainCommand && birdbrainCommand({what!r})")
        except Exception:
            log.exception("Mac: the page didn't take the command")

    def quit(self) -> None:
        self.quitting = True
        if self.ready.is_set():
            self.window.destroy()

"""The "Hide entries by keyword…" window opened from the tray menu,
styled like the list page (theme.py: the Birdbrain theme, Atkinson Hyperlegible)."""
from __future__ import annotations

import ctypes
import tkinter as tk
from tkinter import ttk
from typing import Callable

import theme


def _style(root: tk.Tk, font: str) -> None:
    t = theme.KEYWORD_WINDOW
    root.configure(bg=t["bg"])
    s = ttk.Style(root)
    s.theme_use("clam")  # the only built-in theme that honours custom colors
    flat = dict(bordercolor=t["line"], lightcolor=t["line"], darkcolor=t["line"])
    s.configure(".", background=t["bg"], foreground=t["text"], font=(font, 11), focuscolor=t["focus"])
    s.configure("TFrame", background=t["bg"])
    s.configure("TLabel", background=t["bg"], foreground=t["text"])
    s.configure("Title.TLabel", font=(font, 16, "bold"), foreground=t["head"])
    s.configure("Muted.TLabel", foreground=t["muted"], font=(font, 10))
    s.configure("TEntry", fieldbackground=t["col"], foreground=t["text"], insertcolor=t["text"], padding=6, **flat)
    s.map("TEntry", bordercolor=[("focus", t["focus"])], lightcolor=[("focus", t["focus"])])
    s.configure("TButton", background=t["col"], foreground=t["text"], padding=(14, 6), relief="flat", **flat)
    s.map("TButton", background=[("pressed", t["line"]), ("active", t["hover"])])
    # Primary action in the structure colour: the accent is reserved for overdue work and exams.
    s.configure("Primary.TButton", background=t["struct"], foreground=t["col"], font=(font, 11, "bold"),
                bordercolor=t["struct"], lightcolor=t["struct"], darkcolor=t["struct"])
    s.map("Primary.TButton", background=[("pressed", "#3C3273"), ("active", "#5A4DA3")])


def _title_bar(root: tk.Tk, dark: bool) -> None:
    try:  # Windows 10 20H1+ / 11: DWMWA_USE_IMMERSIVE_DARK_MODE
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(ctypes.c_int(int(dark))), 4)
    except Exception:
        pass


def edit_keywords(keywords: list[str], count: Callable[[str], int], icon=None) -> list[str] | None:
    """Let the user add/remove hidden keywords. `count(k)` says how many
    current entries a keyword hides. `icon` is an optional PIL image for the
    title bar. Returns the new list, or None on Cancel."""
    kws = list(keywords)
    result: dict[str, list[str] | None] = {"value": None}
    t = theme.KEYWORD_WINDOW

    font = theme.tk_font_family()
    root = tk.Tk()
    root.title("Birdbrain: hidden keywords")
    if icon is not None:
        from PIL import ImageTk
        root._icon = ImageTk.PhotoImage(icon, master=root)  # keep a reference
        root.iconphoto(True, root._icon)
    root.attributes("-topmost", True)
    root.resizable(False, False)
    _style(root, font)
    root.update_idletasks()
    _title_bar(root, dark=theme.DEFAULT_MODE == "dark")

    frm = ttk.Frame(root, padding=24)
    frm.grid(sticky="nsew")
    frm.columnconfigure(0, weight=1)
    ttk.Label(frm, text="Hidden keywords", style="Title.TLabel").grid(row=0, column=0, columnspan=3, sticky="w")
    ttk.Label(frm, style="Muted.TLabel", justify="left", text=(
        "Entries whose title or course contains one of these move to the\n"
        "Archived section at the bottom of your list. Case doesn't matter.")).grid(
        row=1, column=0, columnspan=3, sticky="w", pady=(4, 16))

    box = tk.Listbox(frm, height=7, width=52, activestyle="none", selectmode="extended", relief="flat",
                     font=(font, 11), bg=t["col"], fg=t["text"], selectbackground=t["line"],
                     selectforeground=t["text"], highlightthickness=1, highlightbackground=t["line"],
                     highlightcolor=t["focus"], borderwidth=0)
    box.grid(row=2, column=0, columnspan=3, sticky="ew")

    def refresh():
        box.delete(0, "end")
        for k in kws:
            n = count(k)
            box.insert("end", f"  {k}   ({n} {'entry' if n == 1 else 'entries'} hidden)")
        if not kws:
            box.insert("end", "  No hidden keywords yet")
            box.itemconfigure(0, fg=t["muted"])

    entry = ttk.Entry(frm, font=(font, 11))
    entry.grid(row=3, column=0, sticky="ew", pady=(12, 0))

    def add(*_):
        k = " ".join(entry.get().split())
        if k and k.lower() not in (x.lower() for x in kws):
            kws.append(k)
            refresh()
        entry.delete(0, "end")

    def remove():
        for idx in reversed(box.curselection()):
            if idx < len(kws):
                del kws[idx]
        refresh()

    def done():
        result["value"] = kws
        root.destroy()

    ttk.Button(frm, text="Add", command=add).grid(row=3, column=1, padx=(8, 0), pady=(12, 0))
    ttk.Button(frm, text="Remove selected", command=remove).grid(row=3, column=2, padx=(8, 0), pady=(12, 0))
    buttons = ttk.Frame(frm)
    buttons.grid(row=4, column=0, columnspan=3, sticky="e", pady=(24, 0))
    ttk.Button(buttons, text="Cancel", command=root.destroy).grid(row=0, column=0, padx=(0, 8))
    ttk.Button(buttons, text="Done", style="Primary.TButton", command=done).grid(row=0, column=1)

    entry.bind("<Return>", add)
    root.bind("<Escape>", lambda *_: root.destroy())
    refresh()
    entry.focus_force()
    root.mainloop()
    return result["value"]

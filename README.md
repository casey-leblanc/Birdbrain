# Birdbrain

One list of everything you have to do for school, on your own computer.

Birdbrain reads your **Moodle** and your **Outlook** (and Gradescope and McGraw Hill Connect, if your courses
use them), and keeps one list of your assignments, quizzes, exams and events, sorted by day. It keeps scanning
quietly from the system tray (the menu bar on a Mac), so the list is current whenever you look.

> **Birdbrain is a student project. It is not affiliated with, endorsed by or supported by Louisiana State
> University.**

This is the **experimental** version (2.0), being rebuilt on the `birdbrain-experimental` branch. The last
finished version is [1.1.2](https://github.com/casey-leblanc/Birdbrain/releases/tag/v1.1.2).

## Get it

On the [Releases page](https://github.com/casey-leblanc/Birdbrain/releases), open the newest entry marked
**Pre-release** whose name starts "Birdbrain experimental". Nothing else to install, no account to make, and no
key to paste.

**Windows 10 or 11**

1. Download `Birdbrain-…-windows.zip` and unzip it anywhere, for example your Documents folder.
2. Open the `Birdbrain` folder and run `Birdbrain.exe`. Windows may say it doesn't recognise the app, because it
   isn't signed yet: choose **More info**, then **Run anyway**.

**Mac (macOS 12 or newer)**

1. Download the `.dmg` for your Mac: `…-mac-arm64.dmg` for Apple silicon (M1 and later), `…-mac-x64.dmg` for
   Intel. Apple menu › About This Mac says which you have.
2. Open the `.dmg` and drag **Birdbrain** onto **Applications**.
3. Open Birdbrain from Applications. The first time, macOS refuses, because the app isn't signed yet: click
   **Done**, open **System Settings › Privacy & Security**, scroll to **Security**, click **Open Anyway** beside
   Birdbrain's name, and confirm with your password or Touch ID. That is needed once.

Trying it for us? [docs/experimental/TESTING.md](docs/experimental/TESTING.md) is a 25-minute walk through
everything, and [docs/experimental/CHANGES.md](docs/experimental/CHANGES.md) lists what changed since 1.1.2.

## First run

1. Birdbrain asks for your school. LSU is already chosen, so there is nothing to type; at another school, paste
   your Moodle address.
2. A sign-in window opens. Sign in to Moodle and Outlook the way you always do.
3. The window closes by itself and your list fills in. The first scan reads every course page, so give it a few
   minutes.

After that Birdbrain updates itself: Settings › Updates.

## Where your data stays

- **On your computer.** Your list, your settings and your sign-ins are kept in a folder on your computer
  (`%APPDATA%\Birdbrain`; on a Mac, `~/Library/Application Support/Birdbrain`). Birdbrain has no server and no account, and nothing is sent to its author.
- **Your password is never seen by Birdbrain.** You type it only into Moodle's and Microsoft's own sign-in
  pages. Birdbrain keeps the signed-in session those pages give your browser, the same way a browser does.
- **No AI.** Plain rules on your computer read course pages and email previews. Nothing is sent to an AI service.
- **It only reads.** Birdbrain never submits, changes or marks anything on Moodle, Outlook, Gradescope or
  Connect, and it never opens an email, so nothing gets marked as read.
- It talks to the sites you signed in to, and to GitHub to look for a newer version. On first run it also
  downloads, once, the browser it scans with (about 100 MB, from Microsoft's Playwright project). That's all.

## More

The full guide, with everything the list and Settings can do, is [birdbrain/README.md](birdbrain/README.md). It
is also in the zip.

Found a problem? [Open an issue](https://github.com/casey-leblanc/Birdbrain/issues) and say what you did and what
you saw. Please don't paste your course names or anything else personal.

## For developers

```
pip install -r birdbrain/requirements.txt
python -m playwright install chromium
python birdbrain/main.py                 # run from source (Windows or Mac)
python -m unittest discover tests        # unit tests, offline
python -m unittest discover tests/ui     # the list page, driven in a real browser
python build.py                          # on Windows: dist\Birdbrain-<version>-windows.zip
                                         # on a Mac: dist/Birdbrain-<version>-mac-<arm64|x64>.zip and .dmg
```

Every push to `birdbrain-experimental` runs the tests, builds the app on GitHub for Windows and for both kinds of Mac,
starts each for real, performs a real update, and only then publishes a pre-release. Everything that differs
between Windows and a Mac is in `birdbrain/system_win.py` and `birdbrain/system_mac.py`. What's being built and what's left is in
[docs/experimental/CHECKLIST.md](docs/experimental/CHECKLIST.md).

MIT licence: see [LICENSE](LICENSE).

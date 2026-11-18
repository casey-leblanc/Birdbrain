# Birdbrain

One list of everything you have to do for school, on your own computer.

Birdbrain reads your **Moodle** and your **Outlook** (and Gradescope and McGraw Hill Connect, if your courses
use them), and keeps one list of your assignments, quizzes, exams and events, sorted by day. It keeps scanning
quietly from the system tray, so the list is current whenever you look.

> **Birdbrain is a student project. It is not affiliated with, endorsed by or supported by Louisiana State
> University.**

This is the **experimental** version (2.0), being rebuilt on the `birdbrain-experimental` branch. The last
finished version is [1.1.2](https://github.com/casey-leblanc/Birdbrain/releases/tag/v1.1.2).

## Get it

1. On the [Releases page](https://github.com/casey-leblanc/Birdbrain/releases), open the newest entry marked
   **Pre-release** whose name starts "Birdbrain experimental", and download `Birdbrain-…-windows.zip`.
2. Unzip it anywhere, for example your Documents folder.
3. Open the `Birdbrain` folder and run `Birdbrain.exe`. Windows may say it doesn't recognise the app, because it
   isn't signed yet: choose **More info**, then **Run anyway**.

Windows 10 or 11. Nothing else to install, no account to make, and no key to paste. A Mac version is on the way.

## First run

1. Birdbrain asks for your Moodle address (for LSU, `https://moodle.lsu.edu`) and which Outlook you use.
2. A sign-in window opens. Sign in to Moodle and Outlook the way you always do.
3. The window closes by itself and your list fills in. The first scan reads every course page, so give it a few
   minutes.

After that Birdbrain updates itself: Settings › Updates.

## Where your data stays

- **On your computer.** Your list, your settings and your sign-ins are kept in a folder on your PC
  (`%APPDATA%\Birdbrain`). Birdbrain has no server and no account, and nothing is sent to its author.
- **Your password is never seen by Birdbrain.** You type it only into Moodle's and Microsoft's own sign-in
  pages. Birdbrain keeps the signed-in session those pages give your browser, the same way a browser does.
- **No AI.** Plain rules on your computer read course pages and email previews. Nothing is sent to an AI service.
- **It only reads.** Birdbrain never submits, changes or marks anything on Moodle, Outlook, Gradescope or
  Connect, and it never opens an email, so nothing gets marked as read.
- It talks to the sites you signed in to, and to GitHub to look for a newer version. On first run it also
  downloads, once, the browser it scans with (about 100 MB, from Microsoft). That's all.

## More

The full guide, with everything the list and Settings can do, is [birdbrain/README.md](birdbrain/README.md). It
is also in the zip.

Found a problem? [Open an issue](https://github.com/casey-leblanc/Birdbrain/issues) and say what you did and what
you saw. Please don't paste your course names or anything else personal.

## For developers

```
pip install -r birdbrain/requirements.txt
python -m playwright install chromium
python birdbrain/main.py                 # run from source (Windows)
python -m unittest discover tests        # unit tests, offline
python -m unittest discover tests/ui     # the list page, driven in a real browser
python build.py                          # Windows only: builds dist\Birdbrain-<version>-windows.zip
```

Every push to `birdbrain-experimental` runs the tests, builds the app on GitHub, starts it for real, performs
a real update, and only then publishes a pre-release. What's being built and what's left is in
[docs/experimental/CHECKLIST.md](docs/experimental/CHECKLIST.md).

MIT licence: see [LICENSE](LICENSE).

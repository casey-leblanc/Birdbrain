"""Build the app that students download, for the system this is run on.

    python build.py

On Windows: dist/Birdbrain-<version>-windows.zip, holding a Birdbrain folder with Birdbrain.exe. Unzip it anywhere
and run Birdbrain.exe; no Python needed. The sign-in window uses Microsoft Edge, which ships with Windows 10 and
11, and the app window uses Edge's WebView2 runtime. Intermediate files go to %LOCALAPPDATA%\\Birdbrain-build (kept
out of OneDrive).

On a Mac: dist/Birdbrain-<version>-mac-<arm64 or x64>.dmg to open and drag into Applications, and the same app as a
.zip, which is what the app's own updater downloads. One build is for the kind of Mac it was made on: Apple silicon
or Intel. (Not one build for both: the browser driver inside is made for one or the other.) It is signed ad hoc,
not with an Apple Developer ID, so macOS asks before opening it the first time.

On both, the windowless browser the scanner uses (about 100 MB) is fetched once on first run into Playwright's
shared folder. Only the finished files are written into dist/.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "birdbrain"
sys.path.insert(0, str(SRC))
from buildinfo import tag_for  # noqa: E402
from version import VERSION  # noqa: E402
MAC = sys.platform == "darwin"
WORK = (Path(os.environ["LOCALAPPDATA"]) if os.name == "nt" else Path(tempfile.gettempdir())) / "Birdbrain-build"
BUNDLE_ID = "io.github.casey-leblanc.birdbrain"
OUT = ROOT / "dist"


def make_icon(path: Path) -> None:
    sys.path.insert(0, str(SRC))
    import main   # the same icon the tray shows
    main.save_icon(path, (16, 24, 32, 48, 64, 128, 256))   # each size drawn at that size, not shrunk from the biggest


def version_file(path: Path) -> None:
    n = tuple(int(x) for x in VERSION.split(".")) + (0,)
    path.write_text(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={n}, prodvers={n}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('040904B0', [
      StringStruct('FileDescription', 'Birdbrain: assignments, exams and events from Moodle and Outlook'),
      StringStruct('ProductName', 'Birdbrain'), StringStruct('FileVersion', '{VERSION}'),
      StringStruct('ProductVersion', '{VERSION}'), StringStruct('OriginalFilename', 'Birdbrain.exe'),
      StringStruct('InternalName', 'Birdbrain')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])]
)""", encoding="utf-8")


def stamp() -> dict:
    """Which build this is, for the app itself (buildinfo.current): the version and the commit it was built from."""
    commit = os.environ.get("GITHUB_SHA", "")
    if not commit:
        try:
            commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                                    check=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            commit = "local"
    info = {"version": VERSION, "commit": commit[:7], "tag": tag_for(VERSION, commit)}
    (SRC / "assets" / "build.json").write_text(json.dumps(info), encoding="utf-8")
    return info


def licenses_into(folder: Path) -> None:
    folder.mkdir(exist_ok=True)
    for f in (SRC / "assets" / "fonts").glob("OFL-*.txt"):
        shutil.copy(f, folder / f.name)
    shutil.copy(SRC / "assets" / "backgrounds" / "CREDITS.txt", folder / "PHOTO-CREDITS.txt")


def build_mac(info: dict) -> None:
    """Birdbrain.app for the kind of Mac this is run on (Apple silicon or Intel), signed ad hoc so that an Apple
    silicon Mac will start it, as a zip (which the app's own updater reads) and a .dmg (which a person opens). It
    is not signed with a Developer ID or notarized: macOS asks before opening it the first time."""
    import platform
    import plistlib
    arch = "arm64" if platform.machine() == "arm64" else "x64"
    sys.path.insert(0, str(SRC))
    import main   # the same bird the menu bar shows, drawn large for the Dock
    main.make_icon(size=1024).save(WORK / "birdbrain.png")
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
        "--name", "Birdbrain", "--icon", str(WORK / "birdbrain.png"), "--osx-bundle-identifier", BUNDLE_ID,
        "--paths", str(SRC), "--add-data", f"{SRC / 'assets'}:assets",
        "--hidden-import", "pystray._darwin",
        "--distpath", str(WORK / "dist"), "--workpath", str(WORK / "pyi"), "--specpath", str(WORK),
        str(SRC / "main.py"),
    ], check=True)
    app = WORK / "dist" / "Birdbrain.app"
    plist = app / "Contents" / "Info.plist"
    about = plistlib.loads(plist.read_bytes())
    about.update({"CFBundleShortVersionString": VERSION, "CFBundleVersion": VERSION, "CFBundleDisplayName": "Birdbrain",
                  "LSMinimumSystemVersion": "12.0", "LSApplicationCategoryType": "public.app-category.education",
                  "NSHumanReadableCopyright": "A student project. Not affiliated with any university."})
    plist.write_bytes(plistlib.dumps(about))
    shutil.copy(SRC / "README.md", app / "Contents" / "Resources" / "README.md")
    licenses_into(app / "Contents" / "Resources" / "licenses")
    # ad hoc: no Apple account behind it, but a seal every part of the app is under, which Apple silicon insists on
    subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(app)], check=True)
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True)

    OUT.mkdir(exist_ok=True)
    zip_path = OUT / f"Birdbrain-{VERSION}-mac-{arch}.zip"
    dmg_path = OUT / f"Birdbrain-{VERSION}-mac-{arch}.dmg"
    for old in (zip_path, dmg_path):
        old.unlink(missing_ok=True)
    subprocess.run(["ditto", "-c", "-k", "--keepParent", str(app), str(zip_path)], check=True)
    stage = WORK / "dmg"
    stage.mkdir()
    subprocess.run(["ditto", str(app), str(stage / "Birdbrain.app")], check=True)
    os.symlink("/Applications", stage / "Applications")   # drag the bird onto this
    subprocess.run(["hdiutil", "create", "-volname", "Birdbrain", "-srcfolder", str(stage), "-ov", "-format", "UDZO",
                    str(dmg_path)], check=True)
    (SRC / "assets" / "build.json").unlink()   # the source tree stays unstamped
    print(f"\nBuilt {info['tag']} for {arch}: {app}\nZip:  {zip_path} ({zip_path.stat().st_size / 1e6:.0f} MB)\n"
          f"Disk image: {dmg_path} ({dmg_path.stat().st_size / 1e6:.0f} MB)")


def main() -> None:
    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True)
    info = stamp()
    if MAC:
        build_mac(info)
        return
    make_icon(WORK / "birdbrain.ico")
    version_file(WORK / "version.txt")
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
        "--name", "Birdbrain", "--icon", str(WORK / "birdbrain.ico"), "--version-file", str(WORK / "version.txt"),
        "--paths", str(SRC), "--add-data", f"{SRC / 'assets'};assets",
        "--hidden-import", "pystray._win32",
        "--distpath", str(WORK / "dist"), "--workpath", str(WORK / "pyi"), "--specpath", str(WORK),
        str(SRC / "main.py"),
    ], check=True)
    app = WORK / "dist" / "Birdbrain"
    shutil.copy(SRC / "README.md", app / "README.md")
    licenses_into(app / "licenses")

    OUT.mkdir(exist_ok=True)
    zip_path = OUT / f"Birdbrain-{VERSION}-windows.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(app.rglob("*")):
            z.write(f, Path("Birdbrain") / f.relative_to(app))
    size = sum(f.stat().st_size for f in app.rglob("*") if f.is_file())
    (SRC / "assets" / "build.json").unlink()   # the source tree stays unstamped
    print(f"\nBuilt {info['tag']}: {app} ({size / 1e6:.0f} MB unpacked)\n"
          f"Zip:  {zip_path} ({zip_path.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()

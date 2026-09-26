"""Build the distributable Windows app.

    python build.py

Produces dist/Birdbrain-<version>-windows.zip containing a Birdbrain folder with
Birdbrain.exe. Recipients unzip it anywhere and run Birdbrain.exe; no Python needed.
The windowless browser the scanner uses (about 100 MB download) is fetched once on
first run into %LOCALAPPDATA%\\ms-playwright; the sign-in window uses Microsoft Edge,
which ships with Windows 10 and 11.

Intermediate files go to %LOCALAPPDATA%\\Birdbrain-build (kept out of OneDrive);
only the final zip is written into this folder.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

VERSION = "1.0.1"
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "birdbrain"
WORK = Path(os.environ["LOCALAPPDATA"]) / "Birdbrain-build"
OUT = ROOT / "dist"


def make_icon(path: Path) -> None:
    sys.path.insert(0, str(SRC))
    import main   # the same icon the tray shows
    main.make_icon(size=256).save(path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


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


def main() -> None:
    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True)
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
    licenses = app / "licenses"
    licenses.mkdir(exist_ok=True)
    for f in (SRC / "assets" / "fonts").glob("OFL-*.txt"):
        shutil.copy(f, licenses / f.name)
    shutil.copy(SRC / "assets" / "backgrounds" / "CREDITS.txt", licenses / "PHOTO-CREDITS.txt")

    OUT.mkdir(exist_ok=True)
    zip_path = OUT / f"Birdbrain-{VERSION}-windows.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(app.rglob("*")):
            z.write(f, Path("Birdbrain") / f.relative_to(app))
    size = sum(f.stat().st_size for f in app.rglob("*") if f.is_file())
    print(f"\nBuilt {app} ({size / 1e6:.0f} MB unpacked)\nZip:  {zip_path} ({zip_path.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()

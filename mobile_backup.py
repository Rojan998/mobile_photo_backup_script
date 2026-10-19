#!/usr/bin/env python3
"""
mobile_backup.py - Back up photos and videos from any Android phone over ADB.

Copies folders (default: DCIM and Pictures) from the phone to a local folder or
external drive, keeping the folder structure and original file dates. Re-running
only copies new or changed files, so it works for both full and incremental backups.

Examples:
  python mobile_backup.py --dest "D:\\PhoneBackup"
  python mobile_backup.py --dest ~/PhoneBackup --whatsapp
  python mobile_backup.py --dirs /sdcard/DCIM/Camera --dry-run
"""

import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
import time

DEFAULT_DIRS = ["/sdcard/DCIM", "/sdcard/Pictures"]
WHATSAPP_DIRS = ["/sdcard/Android/media/com.whatsapp/WhatsApp/Media"]

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
IS_WINDOWS = os.name == "nt"
ADB_NAME = "adb.exe" if IS_WINDOWS else "adb"

ADB: str = ""  # path to adb, set in main()
SERIAL: str = ""  # device serial, set in main()


# ---------------------------------------------------------------- adb helpers


def find_adb(explicit=None):
    """Locate adb: --adb flag, ADB env var, PATH, next to this script, common SDK paths."""
    home = os.path.expanduser("~")
    candidates = [
        explicit,
        os.environ.get("ADB"),
        shutil.which("adb"),
        *glob.glob(
            os.path.join(SCRIPT_DIR, "platform-tools*", "**", ADB_NAME), recursive=True
        ),
        os.path.join(
            home, "AppData", "Local", "Android", "Sdk", "platform-tools", ADB_NAME
        ),
        os.path.join(home, "Library", "Android", "sdk", "platform-tools", ADB_NAME),
        os.path.join(home, "Android", "Sdk", "platform-tools", ADB_NAME),
        r"C:\platform-tools\adb.exe",
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return None


def adb(*args, device=True):
    """Run an adb command and return stdout; raise RuntimeError on failure."""
    cmd = [ADB]
    if device and SERIAL:
        cmd += ["-s", SERIAL]
    cmd += list(args)
    result = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip())
    return result.stdout


def pick_device(requested=None):
    """Return the serial of the device to use, or exit with a helpful message."""
    out = adb("devices", device=False)
    rows = [line.split() for line in out.strip().splitlines()[1:] if line.strip()]
    ready = [r[0] for r in rows if len(r) >= 2 and r[1] == "device"]
    unauthorized = [r[0] for r in rows if len(r) >= 2 and r[1] == "unauthorized"]

    if requested:
        if requested in ready:
            return requested
        sys.exit(
            f"Device '{requested}' not found or not authorized. Connected: {ready or 'none'}"
        )
    if not ready:
        if unauthorized:
            sys.exit(
                "Phone is connected but not authorized. Unlock it and tap 'Allow' "
                "on the USB debugging popup, then run again."
            )
        sys.exit(
            "No phone found. Check the cable, unlock the phone, and make sure "
            "USB debugging is ON (Settings > Developer options)."
        )
    if len(ready) > 1:
        sys.exit(
            f"Multiple devices connected: {', '.join(ready)}. Choose one with --serial."
        )
    return ready[0]


def device_name():
    """Phone model, e.g. 'SM-S908U', used for the default backup folder name."""
    try:
        model = adb("shell", "getprop ro.product.model").strip()
    except RuntimeError:
        model = ""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", model) or SERIAL or "android"


# ------------------------------------------------------------- file helpers


def list_phone_files(root, include_hidden=False):
    """Return [(phone_path, size_bytes)] for every file under root on the phone."""
    out = adb("shell", f"find '{root}' -type f -exec stat -c '%s|%n' {{}} +")
    files = []
    for line in out.splitlines():
        size, sep, path = line.strip().partition("|")
        if not sep or not size.isdigit():
            continue
        if (
            not include_hidden and "/." in path
        ):  # skips .thumbnails, .cfg, .trashed-* etc.
            continue
        files.append((path, int(size)))
    return files


def safe_part(part):
    """Make a path component valid on Windows."""
    if IS_WINDOWS:
        part = re.sub(r'[<>:"|?*]', "_", part).rstrip(" .")
    return part or "_"


def local_path_for(phone_path, dest):
    """/sdcard/DCIM/Camera/x.jpg -> <dest>/DCIM/Camera/x.jpg"""
    rel = phone_path
    for prefix in ("/sdcard/", "/storage/emulated/0/"):
        if rel.startswith(prefix):
            rel = rel[len(prefix) :]
            break
    rel = rel.lstrip("/")
    return os.path.join(dest, *(safe_part(p) for p in rel.split("/")))


def free_bytes(path):
    """Free space on the drive holding path (walks up to an existing parent)."""
    p = os.path.abspath(path)
    while not os.path.exists(p):
        parent = os.path.dirname(p)
        if parent == p:
            return None
        p = parent
    return shutil.disk_usage(p).free


def gb(n):
    return f"{n / 1e9:.2f} GB"


# ----------------------------------------------------------------------- main


def parse_args():
    ap = argparse.ArgumentParser(
        description="Back up photos/videos from an Android phone over ADB."
    )
    ap.add_argument("--dest", help="Backup folder (default: ./backups/<phone-model>)")
    ap.add_argument(
        "--dirs",
        nargs="+",
        metavar="PATH",
        help=f"Phone folders to back up (default: {' '.join(DEFAULT_DIRS)})",
    )
    ap.add_argument(
        "--add",
        nargs="+",
        metavar="PATH",
        default=[],
        help="Extra phone folders to add to the defaults",
    )
    ap.add_argument(
        "--whatsapp", action="store_true", help="Also back up WhatsApp media"
    )
    ap.add_argument(
        "--serial", help="Device serial (when several phones are connected)"
    )
    ap.add_argument("--adb", help="Path to adb executable")
    ap.add_argument(
        "--include-hidden",
        action="store_true",
        help="Also copy hidden files/folders (e.g. .thumbnails)",
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="Show what would be copied, copy nothing"
    )
    ap.add_argument(
        "--keep-adb", action="store_true", help="Don't stop the adb server at the end"
    )
    return ap.parse_args()


def main():
    global ADB, SERIAL
    args = parse_args()

    found = find_adb(args.adb)
    if not found:
        sys.exit(
            "adb not found. Download Android platform-tools from\n"
            "  https://developer.android.com/tools/releases/platform-tools\n"
            "and unzip it next to this script, add it to PATH, or pass --adb <path>."
        )
    ADB = found

    SERIAL = pick_device(args.serial)
    dest = os.path.abspath(
        os.path.expanduser(
            args.dest or os.path.join(SCRIPT_DIR, "backups", device_name())
        )
    )
    phone_dirs = (
        (args.dirs or DEFAULT_DIRS)
        + args.add
        + (WHATSAPP_DIRS if args.whatsapp else [])
    )

    print(f"Device : {device_name()} ({SERIAL})")
    print(f"Source : {', '.join(phone_dirs)}")
    print(f"Dest   : {dest}")
    print("Scanning phone...")

    all_files = []
    for d in phone_dirs:
        try:
            found = list_phone_files(d, args.include_hidden)
            print(f"  {d}: {len(found)} files")
            all_files += found
        except RuntimeError as e:
            msg = str(e).splitlines()[0] if str(e) else "not found"
            print(f"  {d}: skipped ({msg})")
    todo = []
    for path, size in all_files:
        target = local_path_for(path, dest)
        if os.path.exists(target) and os.path.getsize(target) == size:
            continue  # already backed up
        todo.append((path, size, target))

    total = sum(s for _, s, _ in todo)
    print(
        f"\n{len(all_files)} files found, {len(all_files) - len(todo)} already backed up, "
        f"{len(todo)} to copy ({gb(total)})\n"
    )

    if not todo:
        print("Nothing to do. Everything is already backed up.")
        return
    if args.dry_run:
        for path, size, _ in todo:
            print(f"  {path} ({size / 1e6:.1f} MB)")
        print("\nDry run: nothing was copied.")
        return

    free = free_bytes(dest)
    if free is None:
        sys.exit(
            f"Destination drive for {dest} not found. Is the external drive plugged in?"
        )
    if free < total:
        sys.exit(f"Not enough space: need {gb(total)}, only {gb(free)} free.")

    failed, done, start, current = [], 0, time.time(), None
    try:
        for i, (path, size, target) in enumerate(todo, 1):
            current = target
            os.makedirs(os.path.dirname(target), exist_ok=True)
            short = path.replace("/sdcard/", "")
            print(
                f"[{i}/{len(todo)}] {short} ({size / 1e6:.1f} MB) ...",
                end=" ",
                flush=True,
            )
            try:
                adb("pull", "-a", path, target)  # -a keeps original timestamps
                done += size
                speed = done / 1e6 / max(time.time() - start, 1)
                print(f"ok  ({gb(done)}/{gb(total)}, {speed:.0f} MB/s)")
            except RuntimeError as e:
                print(f"FAILED: {e}")
                failed.append(short)
                if os.path.exists(target):
                    os.remove(target)  # remove partial file so a re-run retries it
            current = None
    except KeyboardInterrupt:
        if current and os.path.exists(current):
            os.remove(current)
        print("\n\nStopped. Run the same command again to resume where you left off.")
        sys.exit(130)

    print(
        f"\nDone in {(time.time() - start) / 60:.1f} min. "
        f"Copied {len(todo) - len(failed)} files ({gb(done)}) to {dest}"
    )
    if failed:
        print(f"{len(failed)} failed. Run the same command again to retry:")
        for f in failed:
            print("  ", f)


if __name__ == "__main__":
    try:
        main()
    finally:
        if ADB and "--keep-adb" not in sys.argv:
            try:
                adb(
                    "kill-server", device=False
                )  # releases the phone so it can be ejected
            except Exception:
                pass

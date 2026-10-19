# Mobile Photo Backup Script

Back up all photos and videos from **any Android phone** to your computer or an external drive using **ADB**. It works on Windows, macOS, and Linux.

## Why?

Copying videos from an Android phone through Windows File Explorer (MTP) often fails with:

> **Error Copying File or Folder — The requested value cannot be determined.**

Small photos usually copy fine, but large videos fail randomly. This script uses `adb pull` instead, which skips MTP entirely and copies files reliably.

Real-world run: **2,618 files / 169 GB copied with zero failures** (Samsung S22 Ultra → external HDD).

## Features

- Works with any Android phone (Samsung, Pixel, OnePlus, Xiaomi, etc.)
- Backs up `DCIM` and `Pictures` by default, plus any folders you choose
- Keeps the phone's folder structure and **original file dates**
- **Incremental and resumable**: re-running copies only new or missing files
- Safe to stop with Ctrl+C: partial files are cleaned up
- Free-space check before copying
- `--dry-run` to preview
- Multiple-device support via `--serial`
- Auto-detects `adb` and releases the phone when done so it ejects cleanly

## Requirements

- **Python 3.7+** (no extra packages needed)
- **Android SDK Platform-Tools** (`adb`): [download](https://developer.android.com/tools/releases/platform-tools)
- An Android phone with **USB debugging** enabled
- A USB data cable
- External drive formatted as **exFAT or NTFS** (FAT32 can't store files over 4 GB)

## Setup

### 1. Enable USB debugging on the phone

1. **Settings → About phone** → tap **Build number** 7 times.
   - Samsung: *Settings → About phone → Software information → Build number*
   - Xiaomi: *Settings → About phone → MIUI version*
2. **Settings → Developer options** → turn on **USB debugging**.

### 2. Get the script and platform-tools

```bash
git clone https://github.com/Rojan998/mobile_photo_backup_script.git
cd mobile_photo_backup_script
```

Download platform-tools for your OS and unzip it **inside this folder**. The script finds `adb` automatically:

```
mobile_photo_backup_script/
├── mobile_backup.py
└── platform-tools-latest-windows/
    └── platform-tools/
        └── adb.exe
```

(Alternatively, put `adb` on your PATH or pass `--adb <path>`.)

### 3. Connect and authorize

1. Plug in the phone and **unlock** it.
2. Close any file manager windows showing the phone.
3. Run the script. On first connection, tap **Allow** on the phone's "Allow USB debugging?" popup (tick *Always allow*), then run it again.

## Usage

```bash
# Back up DCIM + Pictures to an external drive (Windows)
python mobile_backup.py --dest "D:\PhoneBackup"

# macOS / Linux
python3 mobile_backup.py --dest ~/PhoneBackup

# Default destination: ./backups/<phone-model>
python mobile_backup.py

# Also include WhatsApp media (photos, videos, voice notes)
python mobile_backup.py --dest "D:\PhoneBackup" --whatsapp

# Add extra folders on top of the defaults
python mobile_backup.py --add /sdcard/Movies /sdcard/Download

# Only back up specific folders
python mobile_backup.py --dirs /sdcard/DCIM/Camera

# Preview without copying
python mobile_backup.py --dest "D:\PhoneBackup" --dry-run

# Multiple phones connected
python mobile_backup.py --serial R5CT5021L5D
```

### Options

| Option | Description |
|---|---|
| `--dest PATH` | Backup folder (default: `./backups/<phone-model>`) |
| `--dirs PATH ...` | Phone folders to back up (replaces defaults) |
| `--add PATH ...` | Extra phone folders added to the defaults |
| `--whatsapp` | Include `Android/media/com.whatsapp/WhatsApp/Media` |
| `--serial ID` | Device to use when several are connected (`adb devices`) |
| `--adb PATH` | Path to the `adb` executable |
| `--include-hidden` | Also copy hidden files/folders (e.g. `.thumbnails`) |
| `--dry-run` | List what would be copied without copying |
| `--keep-adb` | Don't stop the adb server when finished |

### Example output

```
Device : SM-S908U (R5CT5021L5D)
Source : /sdcard/DCIM, /sdcard/Pictures
Dest   : D:\S22_Backup
Scanning phone...
  /sdcard/DCIM: 2618 files
  /sdcard/Pictures: 42 files

2660 files found, 2618 already backed up, 42 to copy (0.31 GB)

[1/42] Pictures/WhatsApp/IMG-20260901-WA0001.jpg (0.2 MB) ... ok  (0.00/0.31 GB, 30 MB/s)
...
Done in 0.2 min. Copied 42 files (0.31 GB) to D:\S22_Backup
```

### Verify a backup

Run the same command again. A complete backup reports:

```
Nothing to do. Everything is already backed up.
```

## Common phone folders

| Content | Path |
|---|---|
| Camera photos and videos | `/sdcard/DCIM` |
| Screenshots, saved images | `/sdcard/Pictures` |
| Screen recordings / movies | `/sdcard/Movies` |
| Downloads | `/sdcard/Download` |
| WhatsApp media | `/sdcard/Android/media/com.whatsapp/WhatsApp/Media` |
| Telegram | `/sdcard/Android/media/org.telegram.messenger` |

## Tips

- **Keep the phone unlocked** during long transfers, and raise the screen timeout.
- **Disable computer sleep** for large backups.
- **Speed:** ~35 MB/s means USB 2.0, which is typical with in-box phone cables. A USB 3 cable and port can be 2–3× faster.
- **Eject the external drive** properly when done. The script stops adb automatically, so the phone can be unplugged anytime.
- Don't delete anything from the phone until you've verified the backup.

## Troubleshooting

| Problem | Fix |
|---|---|
| `adb not found` | Unzip platform-tools next to the script, add it to PATH, or use `--adb` |
| `No phone found` | Check the cable (must support data), unlock the phone, enable USB debugging |
| `not authorized` | Unlock the phone and tap **Allow** on the popup |
| `Multiple devices connected` | Use `--serial` (see `adb devices`) |
| `Destination drive not found` | Plug in the drive or fix `--dest` |
| Large videos fail | Drive is probably FAT32; use exFAT or NTFS |
| Phone won't eject ("ADB Interface in use") | Run `adb kill-server`, or just unplug; it's safe |
| `python` not found (Windows) | Use `py mobile_backup.py` |

## Limitations

- **Android only.** iPhones don't support ADB.
- Copies files, not app data, contacts, or messages.

## License

MIT
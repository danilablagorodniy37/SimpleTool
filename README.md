# SimpleTool

A Windows 10 and 11 tweaker for privacy, system features and File Explorer. Tick the tweaks you
want, press **Apply**, and press **Revert** to put the original values back.

> **Beta.** This is a test version and it is not stable yet. Use it at your own risk.

The interface is in English, Russian and Ukrainian, with three colour themes (Navy, Midnight and
Light). SimpleTool picks the language of Windows; switch language and theme in the top right corner.

## System overview

At startup SimpleTool scans the system and shows which Windows services related to telemetry,
location, performance, Xbox and security are on, off or not installed. If something cannot be read,
it says why and how to fix it (usually: run as administrator). Every tweak and service has a
detailed explanation, and each tweak lists exactly which registry values, services and tasks it
changes and their current state.

## What it changes

| Category | Tweaks | Examples |
|---|---|---|
| Privacy | 13 | Windows and NVIDIA telemetry, advertising ID, settings sync, data collection tasks, location |
| System | 6 | startup delay, AutoPlay, Ctrl+Shift layout switch, classic Photo Viewer |
| File Explorer | 7 | file extensions, This PC on Win+E, long paths, recent files history, menu delay |
| Context menu | 9 | take ownership, block a program in the firewall, file hashes, copy image, This PC tools |

Every tweak shows its current state: **Applied**, **Partly**, **Not applied**, or **Not found**
when the service or task it targets is not on this PC.

## Run it

You need Windows 10 or 11 and Python 3 with Tkinter (tested with Python 3.12).

```powershell
python main.py
```

Run it as administrator. Without administrator rights SimpleTool says so at startup and locks the
tweaks that change system-wide settings, services and scheduled tasks; per-user tweaks still work.

## Portable version

Build a single `SimpleTool.exe` that runs without Python installed:

```powershell
python build.py
```

The file appears in `dist\SimpleTool.exe`. Copy it to a USB stick and run it on any Windows 10 or 11
PC. Snapshots, backups and settings stay on each PC in `%LOCALAPPDATA%\SimpleTool`, because a
snapshot describes that particular PC and must not travel to another one.

The exe is not code-signed, so the first time Windows SmartScreen may say "Windows protected your
PC": choose **More info → Run anyway**. Some antivirus products flag PyInstaller executables by
mistake.

## Before you apply anything

- SimpleTool changes the registry, services and scheduled tasks. Create a Windows restore point
  first: the **System snapshots** page has a button for it.
- **Snapshots.** SimpleTool saves the state of every setting it can change before each Apply,
  Revert and restore, and keeps the very first snapshot as the original state. Restore any snapshot
  from the **System snapshots** page. Snapshots are JSON files in `%LOCALAPPDATA%\SimpleTool\snapshots`.
- Before a tweak is applied for the first time, its original values are also saved to
  `%LOCALAPPDATA%\SimpleTool\backup.json`. **Revert** restores them; without a backup it sets the
  Windows defaults.
- Some changes take effect after you restart Explorer, sign out or restart the PC.
- On Windows 11 the context menu items are under **Show more options**.

## Development

The repository is public, so every commit is checked for secrets, personal data and files that
must not be published. Turn the pre-commit hook on once per clone:

```powershell
git config core.hooksPath .githooks
python tools/check_secrets.py --history   # manual run over the whole history
```

GitHub Actions runs the same check and [gitleaks](https://github.com/gitleaks/gitleaks) on every
push and pull request.

### Tests

```powershell
python -m unittest discover -s tests -t . -v
```

The tests cannot change your system. Registry access is redirected to a sandbox key
(`HKCU\Software\SimpleToolTest`) and any access outside it fails the test; `sc.exe` and `schtasks.exe`
are replaced with fakes. Inside the sandbox every tweak is applied and reverted, alone and all at
once, and the result must match the original state exactly. A catalog audit checks that no tweak
touches UAC, Defender, Winlogon, startup entries, the boot configuration, critical services or
Windows Update tasks. GitHub Actions runs the tests on Windows for every push.

## License and trademarks

The source code is released under the [MIT License](LICENSE). It is provided as is, without
warranty of any kind: you use SimpleTool at your own risk.

The MIT License does not cover the blagotech brand. The blagotech name, the b!t mark and the
images in [`assets/`](assets/) are trademarks and artwork of blagotech, all rights reserved.
You may not use them to name or identify your own software or services. If you publish a fork or a
modified version of SimpleTool, replace the logo and remove the "by blagotech" label.

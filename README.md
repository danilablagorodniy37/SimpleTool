# SimpleTool

A Windows 10 and 11 tweaker for privacy, system features and File Explorer. Tick the tweaks you
want, press **Apply**, and press **Revert** to put the original values back.

The interface is in English, Russian and Ukrainian. SimpleTool picks the language of Windows and
you can switch it from the globe menu in the top right corner.

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

## Before you apply anything

- SimpleTool changes the registry, services and scheduled tasks. Create a restore point first.
- Before a tweak is applied for the first time, its original values are saved to
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

## License and trademarks

The source code is released under the [MIT License](LICENSE). It is provided as is, without
warranty of any kind: you use SimpleTool at your own risk.

The MIT License does not cover the blagotech brand. The blagotech name, the b!t mark and the
images in [`assets/`](assets/) are trademarks and artwork of blagotech, all rights reserved.
You may not use them to name or identify your own software or services. If you publish a fork or a
modified version of SimpleTool, replace the logo and remove the "by blagotech" label.

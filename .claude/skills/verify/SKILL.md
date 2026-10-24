---
name: verify
description: How to run and drive the SimpleTool exe to verify a change in the real app (update flow, dialogs), on this Windows PC.
---

# Verifying SimpleTool in the real exe

- Build a test exe from the committed source with a *lower* version so the live release counts as an update:
  `git archive HEAD | tar -x -C <scratch>/verify-src`, set `VERSION = "0.6.x.9"` in its main.py, `python build.py`
  there (PyInstaller 6.22.3 is installed in the system Python).
- Run it from its own folder with its own data: set `LOCALAPPDATA` to a scratch folder and write
  `SimpleTool\settings.json` there (`lang`, `terms` = current `terms.VERSION`, `seen_version`, `tray_hint_shown`),
  so the user's settings stay untouched and no terms window appears.
- Only one SimpleTool runs per session: if the user's copy is open, a test exe exits at once. Check
  `Get-CimInstance Win32_Process -Filter "Name='SimpleTool.exe'"` first.
- Pictures: PrintWindow of the window by its exact title (works behind other windows, no focus change).
- Clicks: Tk ignores posted WM_LBUTTON messages (it uses the real pointer), so menus and buttons need a real
  click (SetCursorPos + mouse_event, cursor put back). Ask the user before taking the mouse. A Tk popup menu
  is a `#32768` window; its rectangle gives the item positions (first item about 48 px below the top).
- Onefile processes: a healthy copy is a launcher without python312.dll plus a child app with python312.dll
  from its own `%TEMP%\_MEI*`. Check modules with `(Get-Process -Id <pid>).Modules`.
- Clean up: `taskkill /T /F` the launcher (a forced kill leaves its `_MEI` folder: delete it), never touch
  `%TEMP%\_MEI000021202` or the user's own copy.
- Save .ps1 helpers as UTF-8 with BOM: Windows PowerShell 5.1 reads them as ANSI otherwise and breaks Cyrillic.
- Pictures of pages without the mouse (new cards, texts in ru/uk): `python .claude/skills/verify/shots.py <lang> <out dir> context:classic_menu system:registry_backup:1` builds the window from source with its own LOCALAPPDATA, waits for the scan, switches pages, expands cards, scrolls, and saves PNGs.

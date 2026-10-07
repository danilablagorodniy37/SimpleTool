# SimpleTool

A small Windows tweaker with a window instead of a wall of registry edits.
Pick what you want switched off, press **Применить** (Apply), and SimpleTool runs the
matching PowerShell commands for you. Think of it as a tiny take on tools like
Win 10 Tweaker, with all of its code in one readable file.

The interface is in Russian.

![Python](https://img.shields.io/badge/Python-3-161b22?style=flat-square&logo=python&logoColor=3fb950)
![Tkinter](https://img.shields.io/badge/GUI-Tkinter-161b22?style=flat-square)
![Windows](https://img.shields.io/badge/Windows-10%20%2F%2011-161b22?style=flat-square)

## What it can switch off

The options are grouped into three categories on the left side of the window.

| Category | Option | What runs |
|---|---|---|
| Конфиденциальность (Privacy) | Advertising ID and ads | `AdvertisingInfo\Enabled = 0` in `HKCU` |
| | Windows sync | `SyncSettings\SyncSettings = 0` in `HKCU` |
| | Windows telemetry | `DataCollection\AllowTelemetry = 0` in the `HKLM` policies |
| Система (System) | NVIDIA telemetry | stops the `NvTelemetryContainer` service |
| | Event log collection | stops the `EventLog` service |
| Интерфейс (Interface) | Tooltip color, smaller title bar buttons, no 3D Objects in Explorer | listed in the window, not implemented yet |

## Status next to each option

For options tied to a Windows service, SimpleTool checks that service when you open
the category:

- 🟢 **Применено** (applied): the service is stopped.
- 🔴 **Не применено** (not applied): the service is running.
- ⚪ **Не поддерживается** (not tracked): the option has no service to check.
  The registry options still work when you tick them; their state just isn't read back.

## Run it

You need Windows 10 or 11 and Python 3, which ships with Tkinter.

```powershell
python main.py
```

Run the terminal **as administrator**. Without admin rights the `HKLM` telemetry policy
and stopping services fail.

## Good to know

- Stopping a service lasts until the next reboot. The registry changes stay.
- Stopping `EventLog` also stops Windows from writing its event logs, which tools and
  troubleshooting rely on. Only tick it if you know you want that.
- If the `DataCollection` policy key does not exist on your system yet,
  `Set-ItemProperty` cannot write the value and the telemetry option does nothing.
  Create the key first.
- Nothing is undone automatically. To roll back, set the values back or restart the
  services yourself.

## How it works

Everything lives in [`main.py`](main.py):

- each option is a small function that runs one PowerShell command with `subprocess`;
- `options_functions` maps the option names to those functions;
- `show_options` draws the checkboxes of a category and checks the related service with
  `Get-Service`;
- `apply_settings` runs the ticked options, clears the ticks and refreshes the list.

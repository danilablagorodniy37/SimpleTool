# SimpleTool

A Windows 10 and 11 tweaker for privacy, system features and File Explorer, with a memory limiter
for programs such as Chrome and Discord, a troubleshooting check for lags, crashes and conflicts, and an
uninstaller that finds what programs leave behind. Tick the tweaks you want, press **Apply**, and press
**Revert** to put the original values back.

> **Beta.** This is a test version and it is not stable yet. Use it at your own risk.

**Download:** [blagotech.uk/simpletool](https://blagotech.uk/simpletool/) or the
[latest release](https://github.com/danilablagorodniy37/SimpleTool/releases/latest) on GitHub.

On the first run SimpleTool shows its [terms of use](TERMS.md) and works only after you accept them.
They are shown again if they change; the sidebar has a link to read them at any time. What changed
in each version is in the [changelog](CHANGELOG.md).

SimpleTool goes online only when you ask it to: the **Help** menu at the top of the window has
**Check for updates**, which asks blagotech.uk for the number of the latest version. The same
menu has **What's new** (also shown once after an update) and **Report a problem**: bug reports go to
service@blagotech.uk with the PC's specifications filled in.

The interface is in English, Russian and Ukrainian, with three colour themes (Navy, Midnight and
Light). SimpleTool picks the language of Windows; switch language and theme in the top right corner.

## System overview

At startup SimpleTool scans the system and shows which Windows services related to telemetry,
location, performance, Xbox and security are on, off or not installed; a running service carries a
blue bar along the left edge of its card. If something cannot be read,
it says why and how to fix it (usually: run as administrator). Every tweak and service has a
detailed explanation, and each tweak lists exactly which registry values, services and tasks it
changes and their current state.

## Troubleshooting

The **Troubleshooting** page looks for the usual causes of lags, freezes, crashes and conflicts. It only
reads: nothing is changed and nothing leaves the PC. The check runs the first time the page is opened and takes
a few seconds; **Scan again** repeats it. Every finding says what it means and how to fix it, and most have a
button that opens the right Windows tool or settings page.

| Group | What is checked |
|---|---|
| Performance | memory use and the programs that take most, installed memory and memory Windows cannot use, one memory module, mixed modules or a kit below its rated speed, memory held by drivers (a leak), the page file and the commit limit with the low-memory warnings Windows logs, processor load and its top programs, hardware interrupts that keep a processor busy, the microcode of Intel 13th and 14th Gen processors, AMD's driver for Ryzen 9 X3D processors, the power plan, the power mode, turbo boost and processor caps, a processor that never rests and sleep taken away, the graphics driver (or none: the Microsoft Basic Display Adapter), a disabled graphics card, a monitor plugged into the processor's graphics while a graphics card is installed, a card on too few PCIe lanes, programs set to the power-saving graphics, the refresh rate, the desktop running out of video memory, startup programs and what each costs at the start, what slows the start and the shutdown of Windows (as Windows measures it), several lighting programs at once, background game recording, the network settings Xbox games need (Teredo, the IP Helper service, merged services) and IPv6 turned off, boot options that limit processors or memory, test mode, kernel debugging, a forced HPET timer, Driver Verifier and disabled graphics driver recovery, a desktop slowed down by its firmware, time since the last restart, programs and drivers with documented problems (Nahimic and Sonic Studio, the inpoutx64 driver, Killer and cFosSpeed, an old RivaTuner next to Overwolf, VMware under core isolation, unwanted "optimizers" and "repair tools") |
| Drives | free space, drive health as NVMe drives and hard disks report it themselves, SSD wear (as administrator), Windows on a hard disk, eMMC, a memory card or a USB drive, TRIM turned off for an SSD, an NVMe drive on fewer PCIe lanes or an older generation than it supports, file system errors Windows found, drive and file system errors in the event log, temporary files and who fills them, the servicing log fault that fills the disk |
| Stability | blue screens and what their stop codes usually mean, sudden shutdowns (with the power button held, or a hang while shutting down or going to sleep), program crashes and hangs and the module they crash in (overlays, the graphics driver, the drive, unstable memory or processor settings), graphics driver crashes, NVIDIA driver errors and graphics engine hangs, hardware (WHEA) errors, the last Windows Memory Diagnostic, devices with driver problems or resource conflicts, services that keep failing, important services disabled by "optimization" tools, parts of Windows removed by "debloat" tools (the Store, Windows Security, App Installer, WebView2), damaged system files (as administrator), the recovery environment turned off, WMI not answering or damaged, a clock Windows cannot synchronise, an old or missing Visual C++ runtime, the Media Feature Pack on N editions, battery wear and charge cycles, crash reports that browsers, Electron apps, Steam and game launchers keep outside the Windows log, hangs recovered without a blue screen (live kernel dumps), the dump files of blue screens and of program crashes |
| Protection, updates and network | antivirus (none, out of date, or two at once), threats Microsoft Defender did not remove, exclusions Microsoft names as mistakes and Tamper Protection turned off, UAC, the Spectre and Meltdown mitigations, SmartScreen and the internet mark of downloaded files turned off, Microsoft Defender policies and Windows Security hidden, programs blocked from starting and tools locked by policies, security software blocked in the firewall or by untrusted certificates, the blocklist of vulnerable drivers turned off, memory integrity and its cost in games, UEFI, Secure Boot and TPM 2.0 for anti-cheats and the Secure Boot certificates of 2023, Windows Update (turned off, blocked by policies or another server, paused for months, idle, or updates that keep failing), a pending restart, the end of support of this version of Windows, IP address conflicts and a wired connection at 100 Mb/s, the firewall turned off, SMB1, Remote Desktop without Network Level Authentication or with RDP Wrapper, a proxy server, the hosts file, browser settings forced by policies, root certificates added beyond Microsoft's program, the Guest account or the built-in Administrator turned on, hidden accounts and a stored sign-in password, remote control programs, BitLocker and its recovery key |

Findings are **Problem**, **Warning**, **Note** or **OK**; what could not be read is listed as **Not checked**
with the reason. Most checks work without administrator rights.

## What it changes

| Category | Tweaks | Examples |
|---|---|---|
| Privacy | 13 | Windows and NVIDIA telemetry, advertising ID, settings sync, data collection tasks, location |
| System | 8 | startup delay, AutoPlay, Ctrl+Shift layout switch, classic Photo Viewer, automatic registry backup, detailed sign-in messages |
| File Explorer | 9 | file extensions, This PC on Win+E, long paths, recent files history, menu delay, no Store in Open with, no Spotlight icon |
| Context menu | 11 | classic Windows 11 menu, Copy to and Move to folder, take ownership, block a program in the firewall, file checksums, copy image, This PC tools |

Every tweak shows its current state: **Applied**, **Partly**, **Not applied**, or **Not found**
when the service or task it targets is not on this PC. Applied tweaks carry a teal bar along the left edge
of their card, and each page starts with how many of its tweaks are applied.

## Programs

The **Programs** page lists the installed programs with their own icons (from the program's entry, the icon
Windows Installer keeps for it, or its exe), publisher, version, size and installation date. Search by name or
publisher, and order by name, size or date.

**Uninstall** works like full uninstallers such as Reg Organizer:

1. A Windows restore point first, by the same rule as **Apply**.
2. The program's own uninstaller, which knows what it installed. SimpleTool waits for it and for the copies of
   itself it starts (Inno Setup and NSIS uninstallers quit at once and leave the work to a copy in the temporary
   folder): they run in a job object, which counts them. Windows Installer products are removed with
   `msiexec /x`, not through the repair screen their entries often open.
3. A search for what is left: folders named after the program in Program Files, ProgramData and AppData (Local,
   Roaming, LocalLow and Local\Programs), directly or in its publisher's folder; its install folder; Start menu
   folders and shortcuts, and desktop shortcuts, that lead nowhere now; registry keys named after it under
   Software (its publisher's whole key when nothing else of the publisher is there); startup entries and App
   Paths that start its removed files; its entry in the list, if the uninstaller left it.
4. The list of leftovers, each with a tick box. Registry keys are exported to .reg files before they are deleted,
   removed values are written down, and files and folders go to the Recycle Bin. **Saved copies** opens
   `%LOCALAPPDATA%\SimpleTool\uninstalled`.

Leftovers are matched by the program's own names, never by parts of words. A name another installed program
shares or begins ("python" belongs to every Python), short and generic names, Windows and user folders, the
folders of other installed programs and the folders that hold them, and shared registry keys (Microsoft,
Classes, Policies and the like) are never offered. Files on network drives are not checked: a share that is not
there could keep the list waiting.

An entry whose uninstaller is already gone gets **Remove leftovers**. Programs Windows marks as not removable
(Microsoft Edge) have no button.

SimpleTool remembers the list it read (`%LOCALAPPDATA%\SimpleTool\programs.json`, never sent anywhere). When a
program disappears from it because it was removed through Windows settings or its own uninstaller, SimpleTool
looks for what it left, and if something is there, lists the program at the top of the page with **Remove
leftovers** and **Hide**.

Programs installed for every account are removed with administrator rights, and those installed for one
account without them.

## Memory limiter

The **Memory limiter** page keeps chosen programs within a RAM limit. SimpleTool lists the programs
installed on this PC (from Start menu shortcuts, the installed programs list and known Microsoft Store
apps), with the ones running now first and the memory they use. Pick one, or choose any running
program, then set the limit and the mode:

- **Soft** (default). The limit is for the whole program, all of its processes together. When it is
  exceeded, SimpleTool trims the working sets of the largest processes first until the program is
  back under the limit, and leaves the program alone while it stays within it.
- **Hard.** Windows caps the RAM of every process of the program (a hard working-set maximum). It
  holds the limit firmly, but a program that really needs more memory can slow down. SimpleTool
  removes the caps when you turn the limiter off, switch the program to soft mode, remove it or exit.

Neither mode takes memory away from a program or closes it: pages it is not using right now move out
of RAM to the standby list or the page file, and Windows brings them back when they are needed, which
can cause a short pause. System processes (Explorer, svchost, csrss and others) cannot be added.

The limiter checks the programs every 2–30 seconds while SimpleTool is open. When it is on, closing
the window hides SimpleTool to the notification area; open it again or exit from the tray icon.
Starting SimpleTool a second time shows the running copy instead of starting another one. The list is
saved in `%LOCALAPPDATA%\SimpleTool\limiter.json`. Programs that run as administrator can only be
limited when SimpleTool also runs as administrator.

## Run it

You need Windows 10 or 11 and Python 3 with Tkinter (tested with Python 3.12).

```powershell
python main.py
```

Run it as administrator. Without administrator rights SimpleTool says so at startup and locks the
tweaks that change system-wide settings, services and scheduled tasks; per-user tweaks still work.

Run it from an account that has administrator rights. If a standard user starts SimpleTool with
another account's administrator password, Windows runs it as that other account: per-user settings
(File Explorer, the context menu) and SimpleTool's own data then belong to that account, and
SimpleTool warns about it at startup.

If something goes wrong, SimpleTool writes the details to `%LOCALAPPDATA%\SimpleTool\error.log`.
Send that file to service@blagotech.uk when you report a problem (**Help → Report a problem**).

## Portable version

Build a single `SimpleTool.exe` that runs without Python installed:

```powershell
python build.py
```

The file appears in `dist\SimpleTool.exe`, next to `dist\THIRD-PARTY-NOTICES.txt` with the licences of
Python, Tcl/Tk and PyInstaller that the exe contains; publish both. The build needs Python 3.12 and
uses a pinned PyInstaller. Copy the exe to a USB stick and run it on any 64-bit Windows 10 or 11 PC. Snapshots, backups and settings stay on each PC in `%LOCALAPPDATA%\SimpleTool`, because a
snapshot describes that particular PC and must not travel to another one.

The exe is not code-signed, so the first time Windows SmartScreen may say "Windows protected your
PC": choose **More info → Run anyway**. Some antivirus products flag PyInstaller executables by
mistake.

## Before you apply anything

- SimpleTool changes the registry, services and scheduled tasks. Before it applies anything it asks
  for a Windows restore point: if there is none from the last 24 hours, it offers to create one, and
  turns System Protection on for the Windows drive if it is off. Going on without a restore point
  takes a second warning and a tick that you take the risk. The **System snapshots** page has a
  button for a restore point too.
- **Snapshots.** SimpleTool saves the state of every setting it can change before each Apply,
  Revert and restore. The first time it runs as administrator it also saves the original state,
  which is kept forever, as are the snapshots you make yourself; of the automatic ones the latest 20
  are kept. Restore any snapshot from the **System snapshots** page. Snapshots are JSON files in
  `%LOCALAPPDATA%\SimpleTool\snapshots`.
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

### Releases

The release workflow (`.github/workflows/release.yml`) builds and publishes a version when its tag is
pushed. Nothing is built or uploaded by hand:

1. Set `VERSION` in `main.py` and describe the version in a `## <version>` section of
   [CHANGELOG.md](CHANGELOG.md); a test fails until both match.
2. If the terms of use changed: change `VERSION` in `terms.py` too (SimpleTool then asks everyone to
   accept them again) and run `python tools/terms_md.py`, which writes `TERMS.md` and `terms.json`.
   On the website, `node tools/sync-terms.js` copies `terms.json` into the terms page; deploy it with
   the release.
3. Commit, push, then tag: `git tag v0.6.1` and `git push origin v0.6.1`.

The workflow checks that the tag matches `VERSION`, runs the tests, builds the exe with `build.py`,
signs a build provenance attestation for it, and creates the release with `SimpleTool.exe`,
`THIRD-PARTY-NOTICES.txt` and notes made of the changelog section and the SHA-256. Anyone can check
that a downloaded exe was built by this workflow:

```powershell
gh attestation verify SimpleTool.exe -R danilablagorodniy37/SimpleTool
```

The website's download button, its counter and the update check read the latest release that is not
a prerelease, and the asset named exactly `SimpleTool.exe`. The last step of the workflow warns if
the terms on blagotech.uk are not the ones the program shows.

### Tests

```powershell
python -m unittest discover -s tests -t . -v
```

The tests cannot change your system. Registry access is redirected to a sandbox key
(`HKCU\Software\SimpleToolTest`) and any access outside it fails the test; `sc.exe` and `schtasks.exe`
are replaced with fakes, and so is the service manager. Nothing goes online: the update check is
tested against fake answers. Inside the sandbox every tweak is applied and reverted, alone and all at
once, and the result must match the original state exactly. A catalog audit checks that no tweak
touches UAC, Defender, Winlogon, startup entries, the boot configuration, critical services or
Windows Update tasks. The memory limiter is tested on fake processes and, with real Windows calls,
only on a copy of Python that the test starts under its own unique name, so no other program is
trimmed or capped. The leftover search runs on a made-up profile in a temporary folder with a made-up
registry, and in the window test running an uninstaller and removing leftovers fail the test unless the
test itself replaces them. GitHub Actions runs the tests on Windows for every push.

## License and trademarks

The source code is released under the [MIT License](LICENSE). It is provided as is, without
warranty of any kind: you use SimpleTool at your own risk. The [terms of use](TERMS.md) that the
program shows on the first run say the same in plain words; they are generated from `terms.py` by
`python tools/terms_md.py`.

The MIT License does not cover the blagotech brand. The blagotech name, the b!t mark and the
images in [`assets/`](assets/) are trademarks and artwork of blagotech, all rights reserved.
You may not use them to name or identify your own software or services. If you publish a fork or a
modified version of SimpleTool, replace the logo and remove the "by blagotech" label.

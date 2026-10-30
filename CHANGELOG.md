# Changelog

The release workflow publishes the section of the tagged version as the notes of the GitHub release.

## 0.12

**Troubleshooting: protection and recovery**
- **Microsoft Defender** (new): threats Defender found and could not remove; exclusions Microsoft names as mistakes (whole drives, system, user and temporary folders, every file of a common type, the programs that run scripts) and how many there are; Tamper Protection off on a PC no organization manages. Only where Defender is the antivirus at work. Defender's reports about an edited hosts file are a note.
- **Browser policies** (new): extensions installed by force, the start page, the new tab page, the search engine, the pages opened at start and the proxy, forced by policies in Chrome, Edge, Brave, Chromium, Vivaldi, Yandex Browser and Firefox ("Managed by your organization").
- **Trusted certificates** (new): root certificates added beyond Microsoft's root program, compared with the list Windows keeps and updates.
- **Accounts** (new): the Guest account or the built-in Administrator turned on, an account in use hidden from the sign-in screen, a password for automatic sign-in kept in plain text (only whether it exists; it is never read).
- **Network exposure** (new): the firewall off for private or public networks (unless another firewall is registered), SMB1 installed, Remote Desktop on, without Network Level Authentication, or running another library than Windows' own (RDP Wrapper).
- **Remote control programs** (new, a note): AnyDesk, TeamViewer, RustDesk and others, with a warning about scammers who call "from support".
- **Drive encryption** (new): BitLocker or device encryption of the Windows drive: encrypted but not protected yet, without a recovery password, or protected, with the ID of the recovery key to look up at aka.ms/myrecoverykey.
- **Recovery environment** (new): WinRE turned off, which leaves a PC that does not start without Startup Repair and restore points.
- **Clock** (new): Windows unable to synchronise the clock.
- **Secure Boot** also notes the certificates of 2023 that replace those of 2011, which expired in 2026: a replacement not finished yet, or failed with its error code.
- **Security settings** note the blocklist of vulnerable drivers turned off where memory integrity is off (Windows 11 22H2 and later).

On a PC an organization manages, its policies are notes. Like every check, these only read.

## 0.11

**Troubleshooting: what other tweaking tools left behind**
- **Blocked programs** (new): programs blocked from starting through Image File Execution Options, and the service that fails because of it (Windows Security blocked with systray.exe makes its service fail at every start); tools locked by policies (Task Manager, Registry Editor, the command prompt, Run, Control Panel); security software blocked in the firewall or by untrusted certificates; a program of the sign-in screen that starts something else.
- **Security settings** also look at SmartScreen, the "downloaded from the internet" mark of files, policies that turn Microsoft Defender off (and whether Tamper Protection ignores them), and Windows Security hidden in Settings or its notifications turned off. On a PC an organization manages these are notes.
- **Windows Update** also notes updates taken from another server on a PC no organization manages (a server on the PC itself blocks them all), policies that block Windows Update, and updates paused far beyond the five weeks Settings allows.
- **Disabled services** include Delivery Optimization, the Windows Update medic service and the Security Center, and note the Diagnostic Policy Service and the IP Helper service.
- **Parts of Windows** (new): the Microsoft Store, the Windows Security app, the Windows 11 package of Start, the taskbar and Settings, App Installer, the Xbox sign-in of Game Pass games and the WebView2 runtime, removed by "debloat" tools. The Store is not expected on LTSC.
- **Power plan** also notes a processor that never rests (idle turned off), and sleep taken away by turning Modern Standby off on a PC without another sleep state or by a policy.
- **Network for games** (new): where Xbox gaming is installed, Teredo or the IP Helper service turned off and services merged into shared processes; on any PC, IPv6 turned off with 0xFFFFFFFF (every start waits 5 seconds longer) or at all.
- **WMI** (new): WMI not answering, or its repository damaged according to Windows' own check (as administrator).

**Troubleshooting: drives**
- **Drive health** reads what NVMe drives and SATA hard disks report themselves, as CrystalDiskInfo does: an NVMe drive's critical warning, spare blocks, data errors and how much of its rated endurance is used; a hard disk's reallocated, pending and unreadable sectors (spun-down disks are not woken up). Windows' own counter could show no wear where the drive reports some. Each drive shows its hours on, the data written and its unsafe shutdowns.
- **Drive connection** (new): an NVMe drive on fewer PCI Express lanes or an older generation than it supports, such as a PCIe 4.0 drive in a PCIe 3.0 slot. A slower link is read again while the drive is busy, so a link resting to save power is not taken for a slow slot.
- **File system** (new): volumes Windows marked to be scanned, fixed or repaired, and drives to be checked at the next start. The NTFS event "the volume needs a repair" counts among drive errors.

**Troubleshooting: starts and load**
- **Startup time** (new): how long Windows takes to start, and the drivers, services and devices Windows itself names as slowing several starts or the shutdown down.
- **Startup programs** name the programs that cost the most at the last starts, as Task Manager's "Startup impact" counts it.
- **Processor load** also measures hardware interrupts and deferred procedure calls: a driver that keeps one processor busy with them makes sound crackle and games stutter while the total load looks low.
- **Video memory** (new): the desktop running out of video memory, as Windows records it.
- **Blue screens** say what each stop code usually points to; **battery wear** shows the charge cycles where the laptop reports them. Drive sizes of a terabyte and more are shown in TB.

The check takes about a second longer.

## 0.10.3

- **Smooth circles.** Tk draws circles and arcs without antialiasing, so the ring on the tweaks tile, the scan animation and the activity indicator in the footer looked jagged. The scan animation and the indicator are now drawn through Windows' own GDI+ (no extra library) into images, frame by frame and kept for the loop; the ring is computed pixel by pixel with soft edges, like the gradient buttons. Without GDI+ the old drawing stays as a fallback.

## 0.10.2

- **Colored tiles.** The tiles at the top of System overview and Troubleshooting are tinted and framed in their own color: blue for services on, teal for tweaks applied and findings in order, orange for warnings, red for problems. A tile whose count is zero stays plain.
- **A ring for tweaks applied.** The tweaks tile is a third wider and shows the share of applied tweaks as a ring in the brand gradient, with the percentage inside; it fills up with the count.

## 0.10.1

**Crisper text**
- On Windows 11 the interface uses Segoe UI Variable Text, the system font cut for small sizes; Windows 10 keeps Segoe UI. Descriptions, notes and the sidebar are one step larger (10 and 11 pt instead of 9 and 10), card titles and dialog headings too, so the hierarchy of a card is clearer.
- Secondary text, counters and card borders have more contrast in all three themes.

**System overview**
- The card of a running service carries a blue bar along its left edge, like applied tweaks carry a teal one; a service that could not be checked carries an orange bar. Services that are off or not installed stay plain.

## 0.10

**Interface**
- **Pages read at a glance.** Every tweak page starts with "Applied: N of M" and a gradient bar that fills up. Applied tweaks carry a teal bar along the left edge of their card and partly applied ones an orange bar; troubleshooting findings carry a red, orange or blue bar by severity, and their badges are tinted the same way.

**Tweaks**
- **Turn off settings sync** also sets the Windows policy "Do not sync" (Pro, Enterprise and Education), which turns the whole "Remember my preferences" feature of Windows 11 off and greys out its switch. Windows 11 creates the per-group switches only for Microsoft accounts, so on a local account the tweak changed nothing visible. The tweak now needs administrator rights; applied with an earlier version it shows **Partly**: select it and press **Apply**.
- **Turn off Microsoft experiments** says that it also turns off Known Issue Rollback, Microsoft's way of switching off a change of an update that causes problems, and what to do then.
- **Turn off Steps Recorder** shows **Not found** on a PC where Microsoft has already removed Steps Recorder (deprecated since 2023), and its description says what the lock screen camera policy is for.

**Troubleshooting**
- **Drive errors** of a disk that is not on the PC any more, such as a memory stick or phone unplugged since, are a note rather than a problem. Before, they were taken for errors of an internal drive.

## 0.9

**Troubleshooting**
- **Crash reports outside the Windows log.** Browsers built on Chromium (Chrome, Edge, Brave, Opera, Vivaldi), programs built on Electron (Discord, Visual Studio Code, Teams, Slack, Signal, WhatsApp), Steam, the Epic Games and Riot launchers, OBS, Telegram, Firefox and others catch their own crashes and close the process before Windows notices, so Event Viewer and Reliability Monitor never see them. SimpleTool now counts the reports of the last 14 days in their crash folders, and the reports waiting in Windows Error Reporting.
- **Hangs recovered without a blue screen.** The live kernel dumps in C:\Windows\LiveKernelReports: a graphics driver or card that stopped responding (WATCHDOG), a network driver (NDIS), a USB controller, a hang while going to sleep or waking up. They stay on disk when Windows Error Reporting is off and the log has nothing. Reading them needs administrator rights; without them SimpleTool names the components the registry remembers.
- **Programs with documented problems.** Audio software that crashes games at start (Nahimic, Sonic Studio), the inpoutx64 driver of lighting and monitoring tools that Microsoft blocks since August 2026 because games crash with it, Killer and cFosSpeed network tools, an old RivaTuner next to Overwolf, VMware slowed down by core isolation, Corsair Link next to iCUE, an old Logitech Gaming Software next to G HUB, Armoury Crate with an Intel Arc card, and "optimizers", driver updaters and "repair tools" that antivirus makers flag or regulators fined. Every line says what was reported and what to do; SimpleTool removes nothing itself.
- **Program crashes** also show the crash dumps Windows Error Reporting saved locally for a program (their number, size and folder), and advise clearing the shader cache when a program crashes inside the graphics driver. Graphics driver crashes get the same advice.
- **Blue screens** have a second witness for when the log was cleared: the dump files in C:\Windows\Minidump and the date of the last crash Windows remembers. A note when saving of crash dumps is turned off, and the size of MEMORY.DMP when it is over a gigabyte.
- **Temporary files** now name who litters: the biggest folders and the families of loose files with the same name, warn from 20 000 files, and recognise the servicing log fault that fills the disk with cab_* files.
- All of this only reads files and the registry and takes milliseconds; the temporary folder keeps its time budget.

## 0.8

**New tweaks**
- **Classic right-click menu** (Windows 11): the full menu opens at once, with no “Show more options”. SimpleTool restarts Explorer after applying or reverting it, so the change shows immediately; open folder windows close for a moment.
- **Copy to folder and Move to folder** in the right-click menu of files and folders: Windows' own commands, registered for the current user.
- **No Microsoft Store in “Open with”**: the dialog for files of an unknown type no longer offers to look for an app in the Store (the Windows policy for it; the Store itself keeps working).
- **No “Learn about this picture” icon** (Windows 11): hides the Windows Spotlight icon on the desktop the way Windows hides the Recycle Bin; the pictures keep changing.
- **Automatic registry backup**: Windows keeps a copy of the registry in RegBack again, as it did before version 1803, for repairs from the recovery environment. Microsoft's documented value; the first copy is made after a restart, and the RegIdleBackup task refreshes it during automatic maintenance.
- **Detailed sign-in and shutdown messages**: Windows shows each step while signing in, signing out and shutting down, so a slow step can be seen.

**Interface**
- After Apply and Revert the message says what a change still needs: Explorer was restarted, sign out and back in, or restart the PC. Before, it always said that some changes may need a restart. Switching the keyboard layout hotkey and the menu delay are marked as needing a sign-out.
- Explorer is restarted only in the current session and with the user's own environment, not SimpleTool's, so programs started from the taskbar do not inherit anything from it. When SimpleTool runs under another account's password, it asks to sign out instead.

## 0.7

**Troubleshooting**
- A new page looks for the usual causes of lags, freezes, crashes and conflicts. It only reads: memory and processor counters, drives, the registry, the hosts file and the Windows event logs. Nothing is changed and nothing leaves the PC; most checks work without administrator rights.
- Performance: memory use and the programs that take most, installed memory and memory Windows cannot use, a single memory module, mixed modules or a kit running below its rated speed (XMP/EXPO off), memory held by drivers (a leak in the non-paged pool), the page file (off, too small, on a missing or full drive), the commit limit and the low-memory warnings Windows logs with the programs to blame, processor load and its top programs, the microcode of Intel 13th and 14th Gen desktop processors (Vmin shift), AMD's 3D V-Cache driver and the Game Bar for Ryzen 9 X3D processors, the power plan, the Windows 11 power mode, turbo boost and caps on the processor's state or frequency, the graphics driver (a card running on the Microsoft Basic Display Adapter, a card disabled in Device Manager, NVIDIA drivers that lose FPS with the October 2025 Windows update), a monitor plugged into the processor's graphics while a graphics card is installed, a card on too few PCIe lanes, programs set to the power-saving graphics, the refresh rate, startup programs, several lighting programs running at once, background game recording, boot options that limit processors or memory, test mode, kernel debugging, a forced HPET timer, Driver Verifier and disabled graphics driver recovery, a desktop slowed down by its firmware, time since the last restart.
- Drives: free space, drive health and, as administrator, SSD wear and read errors, Windows on a hard disk, eMMC, a memory card or a USB drive, TRIM turned off for an SSD, drive and file system errors in the event log (errors of pulled-out memory sticks are only noted), temporary files.
- Stability: blue screens and sudden shutdowns (and whether the power button was held or Windows hung while shutting down or going to sleep), program crashes and hangs with the module they crash in (an overlay, the graphics driver, a drive read error, unstable memory or processor settings), graphics driver crashes, NVIDIA driver errors and graphics engine hangs, hardware (WHEA) errors (corrected processor and memory errors are a warning), the last Windows Memory Diagnostic result, devices with driver problems or resource conflicts, services that keep failing, important services turned off by "debloat" tools and a clock that never synchronises, damaged system files (as administrator), an old or missing Visual C++ runtime, the Media Feature Pack on N editions, battery wear.
- Protection, updates and network: no antivirus, an out-of-date one or two at once, UAC and the Spectre and Meltdown mitigations turned off, memory integrity and what it costs in games, UEFI boot, Secure Boot and TPM 2.0 (a warning when Riot Vanguard is installed), Windows Update turned off or idle (by the date of the last monthly update) and Windows updates that keep failing (Microsoft Store apps and Defender's definitions, which retry by themselves, are left out), a pending restart, the end of support of this version of Windows (Windows 11 up to 26H1 and 26H2), IP address conflicts and a wired connection at 100 Mb/s, a proxy server, a hosts file that blocks addresses Windows needs.
- The whole check takes about three seconds. The event logs are read so that a flood of one kind of event does not hide the others, and drivers this PC does not have are no reason for a log query to fail.
- Each finding is a Problem, a Warning, a Note or OK, explains what it means and how to fix it, and offers a button that opens the right Windows tool or settings page. The sidebar counts the problems and warnings.

**Interface**
- In a short window the sidebar items move closer together, so the bottom of the sidebar stays in view.

## 0.6.4

- **Clean restart after an update.** The portable exe unpacks itself into a temporary folder, and a copy started with the running copy's environment ran from that copy's folder instead of its own: the previous version stayed in the background, SimpleTool.exe.old could not be deleted, and the folder the new version ran from was due to be deleted under it. SimpleTool now starts the new version with `PYINSTALLER_RESET_ENVIRONMENT`, so it unpacks itself anew.
- An update installed by 0.6.3 still starts the new version the old way; 0.6.4 notices (its parent process runs Python, which the onefile launcher never does) and starts itself once more, cleanly.
- **Restart as administrator** passes the same setting, for PCs where Windows elevates without asking (UAC off).

## 0.6.3

**Updates in one click**
- The update window has **Update**: SimpleTool downloads the new SimpleTool.exe from its GitHub releases, checks its size and SHA-256 against the release, puts it in place of the running exe (which Windows lets it rename) and restarts into it. Settings, backups and snapshots stay where they are; the previous exe is deleted once it has exited. If anything fails, the running version is untouched and the window offers the manual download.
- Only the portable exe updates itself, and only a release with a published SHA-256. Run from the source code, SimpleTool still sends you to the download page.

**A daily check**
- Once a day at start SimpleTool quietly asks blagotech.uk whether a new version is out. If there is one, Help gets a dot, its menu an **Update to …** item, and a notification says so; no window opens. **Help → Check for updates daily** turns the check off.

**Terms of use**
- Section 7 describes the daily check, the download from GitHub and the specifications in problem reports, so SimpleTool asks you to accept the terms again.

## 0.6.2

- **Help** button at the top of the window instead of an unnamed ⓘ icon: Check for updates, What's new, Report a problem and the terms of use.
- **What's new** after an update: SimpleTool shows once what changed since the version that ran before. Help → What's new shows it again.
- **Report a problem** adds the PC's specifications to the letter — processor, graphics card, memory, PC model, Windows edition and build, SimpleTool's version, rights and display scale — and shows them in the window before anything is sent. They are read from the registry; nothing goes online by itself.

## 0.6.1

**A Windows restore point before every Apply**
- When there is no restore point from the last 24 hours, SimpleTool offers to create one before it applies tweaks. If System Protection is off for the Windows drive, it turns it on for that.
- You can go on without a restore point only through a second warning, after ticking that you take the risk.
- Without administrator rights SimpleTool explains that Windows creates restore points only for administrators and offers to restart as one.

**Updates and bug reports**
- New menu behind the ⓘ button at the top of the window: **Check for updates**, **Report a problem** and the terms of use.
- **Check for updates** is the only time SimpleTool goes online: it asks blagotech.uk for the number of the latest version. If there is a newer one, **Download** opens it in your browser.
- **Report a problem** writes an email to service@blagotech.uk with the SimpleTool and Windows versions filled in, and shows `error.log` to attach. The error window offers it too.
- The terms of use say this (sections 3, 7 and 11), so SimpleTool asks you to accept them again.

**Fixes**
- Services are disabled through the Windows service manager, so the change applies at once. Before, the Device Management WAP Push service could start again until the next restart, although it showed as applied.
- Deleting a snapshot asks first.
- Switching pages is faster on high-DPI screens: the header glow took up to half a second to draw at 200%.
- The memory limiter says that SimpleTool exits on close when it is on but has nothing to limit.
- The window can be closed while Windows creates a restore point. Console programs SimpleTool runs time out instead of hanging.

## 0.6

**Security**
- Context menu items that work on a file (file hashes, copy image, take ownership, block in the firewall) no longer put the file path into PowerShell code. A file name with an apostrophe broke them, and a specially crafted file name could run commands. If you applied these items with an earlier version they now show **Partly**: select them and press **Apply** to write the new commands.
- The "Restart in Safe Mode with Command Prompt" item is removed: Windows would start a command prompt instead of Explorer on every boot.

**Terms of use** on the first run, in all three languages, with a link in the sidebar.

**Safer backups and snapshots**
- The original values are saved to disk before anything changes, and files are written so that a crash or power cut cannot leave them half-written. A damaged backup is kept aside instead of being overwritten.
- Scheduled tasks whose state could not be read are no longer recorded as enabled.
- The original-state snapshot is taken the first time SimpleTool can read everything (as administrator), even if you made snapshots before.

**Reliability**
- An unexpected error no longer freezes the window or the tray icon. Details go to `%LOCALAPPDATA%\SimpleTool\error.log`: attach it when you report a problem.
- Restart as administrator no longer leaves a temporary folder behind.
- Memory limiter: hard limits are removed at the next start if SimpleTool was closed from Task Manager or crashed; a damaged settings file no longer stops SimpleTool from starting; one running copy also across administrator rights; the tray icon comes back after Explorer restarts.
- A warning when SimpleTool runs under another account than the one signed in to Windows.
- The window fits small screens; status badges moved to the bottom of the cards; text fixes in all languages.

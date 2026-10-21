# Changelog

The release workflow publishes the section of the tagged version as the notes of the GitHub release.

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

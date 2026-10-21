"""English texts."""

TEXTS = {
    "ui": {
        "by": "by",
        "language": "Language",
        "theme": "Theme",
        "admin_yes": "Administrator",
        "admin_no": "Limited mode",
        "apply": "Apply",
        "revert": "Revert",
        "select_all": "Select all",
        "clear": "Clear",
        "rescan": "Scan again",
        "selected": "Selected: {n}",
        "hint_select": "Select tweaks to apply or revert.",
        "checking": "Scanning the system…",
        "working_apply": "Applying…",
        "working_revert": "Reverting…",
        "done_apply": "Applied: {n}. Some changes take effect after restarting Explorer or the PC.",
        "done_revert": "Reverted: {n}.",
        "nothing_to_apply": "The selected tweaks are already applied.",
        "nothing_to_revert": "The selected tweaks are not applied, there is nothing to revert.",
        "errors_title": "Some changes failed",
        "errors_intro": "These changes could not be made:",
        "close": "Close",
        "terms_link": "Terms of use",
        "terms_accept": "I accept",
        "terms_exit": "Exit",
        "back": "Back",
        "update_link": "Check for updates",
        "update_checking": "Checking for updates…",
        "update_latest": "You have the latest version, {version}.",
        "update_title": "Update available",
        "update_heading": "SimpleTool {version} is available",
        "update_text": "You have version {current}. Download the new SimpleTool.exe and run it instead of this one: "
                       "settings, backups and snapshots stay where they are. Close this copy first.",
        "update_download": "Download",
        "update_notes": "What's new",
        "update_later": "Later",
        "update_failed_title": "Could not check for updates",
        "update_failed_text": "SimpleTool got no answer from blagotech.uk: {error}\n\nCheck the internet "
                              "connection, or look for a new version on the website.",
        "update_open_site": "Open the website",
        "report_link": "Report a problem",
        "report_title": "Report a problem",
        "report_text": "Found a bug, or did something go wrong? Write to the address below: what you did, what you "
                       "expected and what happened. If SimpleTool saved an error log, attach it: “Open error log” "
                       "shows the file. The letter already has your PC's specifications, shown below: they help to "
                       "find the cause.",
        "report_write": "Write an email",
        "report_log": "Open error log",
        "report_copy": "Copy address",
        "report_copied": "Address copied: {email}",
        "report_subject": "SimpleTool {version}: a problem",
        "report_body": "{system}\n\nWhat I did:\n\n\nWhat happened:\n\n\n(Attach error.log if there is one.)\n",
        "rp_checking": "Checking Windows restore points…",
        "rp_gate_title": "First, a restore point",
        "rp_gate_text": "SimpleTool is about to change Windows settings. If something goes wrong, a Windows restore "
                        "point is the reliable way back: it saves the whole registry and system files, and System "
                        "Restore can return to it even when Windows does not start.\n\nThere is no restore point "
                        "from the last 24 hours. Creating one takes a minute or two. If System Protection is off "
                        "for the Windows drive, SimpleTool turns it on.",
        "rp_gate_admin_text": "SimpleTool is about to change Windows settings. Before that it creates a Windows "
                              "restore point: the reliable way back if something goes wrong. Windows lets only "
                              "administrators create restore points.\n\nRestart SimpleTool as administrator: it "
                              "creates the restore point, and then you apply the tweaks.",
        "rp_gate_create": "Create restore point and apply",
        "rp_gate_skip": "Continue without a restore point…",
        "rp_open_protection": "Open System Protection settings",
        "rp_done_enabled": "System Protection turned on, Windows restore point created.",
        "rp_skip_title": "Without a restore point you are on your own",
        "rp_skip_text": "If a change breaks Windows, there may be no way back: you may lose programs, settings or "
                        "files and have to reinstall Windows.\n\nSimpleTool is provided as is, without any warranty "
                        "(see the terms of use). Neither SimpleTool nor blagotech can repair your system.",
        "rp_skip_confirm": "I understand the risk. Whatever happens to my computer is my own responsibility.",
        "rp_skip_apply": "Apply without a restore point",
        "snap_delete_title": "Delete this snapshot?",
        "snap_delete_text": "The snapshot from {date} will be deleted for good: you will not be able to restore it.",
        "snap_delete_ok": "Delete",
        "mem_on_idle_text": "Nothing is being limited yet: add a program below or turn one on. Until then, closing "
                            "the window exits SimpleTool.",
        "help": "Help",
        "whatsnew_link": "What's new",
        "whatsnew_title": "What's new in SimpleTool {version}",
        "whatsnew_intro": "SimpleTool has been updated. Here is what changed:",
        "whatsnew_all": "All changes on GitHub",
        "whatsnew_ok": "Got it",
        "report_specs": "Your PC (added to the letter):",
        "report_copy_specs": "Copy",
        "report_copied_specs": "PC specifications copied.",
        "update_install": "Update",
        "update_text_install": "You have version {current}. SimpleTool downloads the new version, checks it and "
                               "restarts; settings, backups and snapshots stay where they are.",
        "update_preparing": "Preparing the update…",
        "update_downloading": "Downloading the update… {percent}%",
        "update_busy": "Wait until the current operation finishes.",
        "update_install_failed_title": "The update was not installed",
        "update_install_failed_text": "{error}\n\nThis version keeps working. You can download the new one by hand.",
        "update_download_manual": "Download by hand",
        "update_restart_failed": "The update is installed, but SimpleTool could not start again: {error}. Start "
                                 "SimpleTool.exe yourself.",
        "update_available_toast": "SimpleTool {version} is out: Help → Update",
        "update_install_menu": "Update to {version}",
        "update_daily": "Check for updates daily",
        "crash_title": "Something went wrong",
        "crash_intro": "SimpleTool hit an unexpected error and keeps working. If something looks wrong, restart it. "
                       "The details are saved in the error log, "
                       "please send it to {email}:",
        "start_failed": "SimpleTool could not start: {error}\n\nThe details are saved in {path}. Please send "
                        "this file to {email}.",
        "other_account_title": "SimpleTool runs as another account",
        "other_account_text": "SimpleTool was started as {account}, but Windows is signed in as {user}. Settings of "
                              "the current user (File Explorer, the context menu, privacy settings of the account) "
                              "will change for {account}, not for {user}, and backups are saved in that account's "
                              "folder.\n\nTo change your own settings, sign in to an account with administrator "
                              "rights and run SimpleTool there.",
        "mem_denied_protected": "No access to processes: {count}. Windows protects them, so they cannot be limited.",
        "admin_title": "Administrator rights needed",
        "admin_text": "SimpleTool is running without administrator rights. Tweaks that change system-wide "
                      "settings, services and scheduled tasks are locked.\n\nRestart SimpleTool as "
                      "administrator to use every tweak.",
        "admin_restart": "Restart as administrator",
        "admin_continue": "Continue without rights",
        "admin_failed": "Could not restart as administrator.",
        "status_applied": "Applied",
        "status_partial": "Partly",
        "status_not_applied": "Not applied",
        "status_unavailable": "Not found",
        "status_admin": "Admin only",
        "status_checking": "Checking…",
        "status_unknown": "Unknown",
        "details_show": "Details",
        "details_hide": "Hide details",
        "what_changes": "What changes",
        "backup_saved": "Original values are saved. Revert restores exactly them.",
        "backup_none": "No backup yet: the first Apply saves the current values. Without a backup, Revert sets the "
                       "Windows defaults.",
        "op_value": "{path} → {name} = {data}",
        "op_default_name": "(Default)",
        "op_label": "menu text",
        "op_key": "Registry key {path}",
        "op_service": "Service {name}: startup type Disabled, stopped",
        "op_task": "Scheduled task {path}: disabled",
        "op_shortcut": "Desktop shortcut “{name}”",
        "op_missing": "not on this PC",
        "op_missing_many": "Not on this PC, will be skipped: {n}",
        "op_unknown": "could not check",
        "scan_title": "Scanning the system",
        "scan_text": "SimpleTool reads services, registry settings and scheduled tasks. Nothing is changed.",
        "scan_services": "Windows services",
        "scan_registry": "Registry settings",
        "scan_tasks": "Scheduled tasks",
        "summary_on": "Services on",
        "summary_off": "Services off",
        "summary_missing": "Not installed",
        "summary_unknown": "Could not check",
        "summary_tweaks": "Tweaks applied",
        "unknown_title": "Some things could not be checked",
        "unknown_intro": "They are marked Unknown. Here is why and how to fix it:",
        "service_on": "On",
        "service_off": "Off",
        "service_missing": "Not installed",
        "service_unknown": "Unknown",
        "startup": "Startup: {start}",
        "now": "now {state}",
        "start_0": "boot",
        "start_1": "system",
        "start_2": "automatic",
        "start_2d": "automatic (delayed)",
        "start_3": "manual",
        "start_4": "disabled",
        "start_unknown": "unknown",
        "run_1": "stopped",
        "run_2": "starting",
        "run_3": "stopping",
        "run_4": "running",
        "run_5": "resuming",
        "run_6": "pausing",
        "run_7": "paused",
        "run_unknown": "state unknown",
        "service_name": "Service name: {name}",
        "managed_by": "Changed by the tweak “{name}” →",
        "beta": "BETA",
        "beta_note": "Test version, not stable yet. Use it at your own risk.",
        "snap_intro": "A snapshot records every setting SimpleTool can change: registry values, services, scheduled "
                      "tasks, context menu items and shortcuts. SimpleTool takes one automatically before every Apply, "
                      "Revert and restore, and keeps the very first one as the original state. Restoring a snapshot "
                      "returns all of these settings to how they were at that moment.",
        "snap_rp_hint": "A Windows restore point goes further: Windows saves the whole registry and system files, "
                        "and you can return to it through System Restore (Control Panel → Recovery), or from the "
                        "Windows recovery environment if Windows does not start. It needs administrator rights; if "
                        "System Protection is off for the Windows drive, SimpleTool turns it on. By default Windows "
                        "allows one per day. Before Apply SimpleTool asks for a restore point when there is none "
                        "from the last 24 hours.",
        "snap_create": "Take snapshot",
        "snap_restore_point": "Create Windows restore point",
        "snap_folder": "Open snapshots folder",
        "snap_restore": "Restore",
        "snap_delete": "Delete",
        "snap_empty": "No snapshots yet. The first one is taken right after the scan.",
        "snap_empty_limited": "No snapshots yet. The original state is saved the first time SimpleTool runs as "
                              "administrator, and you can take a snapshot now.",
        "kind_initial": "Original state",
        "kind_before_apply": "Before Apply",
        "kind_before_revert": "Before Revert",
        "kind_before_restore": "Before restore",
        "kind_manual": "Taken manually",
        "snap_summary": "Tweaks applied: {applied} of {total}  ·  settings saved: {ops}",
        "snap_initial_note": "How the PC was before SimpleTool changed anything. Kept permanently.",
        "snap_confirm_title": "Restore this snapshot?",
        "snap_confirm_text": "SimpleTool will return all of its settings to how they were on {date}. A new snapshot is "
                             "taken first, so you can undo this too. Some changes take effect after restarting Explorer "
                             "or the PC.",
        "snap_confirm_ok": "Restore",
        "cancel": "Cancel",
        "snap_working": "Restoring the snapshot…",
        "snap_saving": "Taking a snapshot…",
        "snap_saved": "Snapshot saved.",
        "snap_restored": "Settings restored to the snapshot from {date}.",
        "snap_admin": "Restoring snapshots and restore points needs administrator rights.",
        "rp_working": "Creating a Windows restore point… This can take a minute.",
        "rp_done": "Windows restore point created.",
        "rp_failed": "Windows did not create a restore point.",
        "snap_failed": "Could not save the snapshot.",
        "mem_on": "Memory limiter is on",
        "mem_off": "Memory limiter is off",
        "mem_on_text": "Programs are checked every {seconds} s. When you close the window, SimpleTool keeps working "
                       "in the tray.",
        "mem_off_text": "Turn it on to keep the programs below within their limits.",
        "mem_interval": "Check every",
        "mem_seconds": "{n} s",
        "mem_freed": "Freed so far",
        "mem_apps": "Programs",
        "mem_add": "Add a program",
        "mem_installed_hint": "Programs installed on this PC. The ones running now come first, with the memory "
                              "they use.",
        "mem_installed_loading": "Looking for programs installed on this PC…",
        "mem_installed_empty": "No other installed programs were found. Choose one from the running programs.",
        "mem_show_all": "Show all ({n})",
        "mem_show_less": "Show fewer",
        "mem_pick": "Choose from running…",
        "mem_now": "Now {size}, processes: {count}",
        "mem_idle": "Not running",
        "mem_denied": "No access to processes: {count}. Run SimpleTool as administrator.",
        "mem_largest": "largest process {size}",
        "mem_procs": "processes: {n}",
        "mem_added": "Added",
        "mem_limit": "Limit",
        "mem_soft": "Soft",
        "mem_hard": "Hard",
        "mem_soft_hint": "When the program as a whole uses more than the limit, SimpleTool moves its unused memory "
                         "out of RAM.",
        "mem_hard_hint": "Windows keeps each process of the program below the limit in RAM. Stronger, but the program "
                         "can slow down.",
        "mem_remove": "Remove",
        "mem_empty": "No programs yet. Add one below.",
        "mem_how_title": "How it works",
        "mem_how": "SimpleTool does not take memory away from a program. It moves pages the program is not using right "
                   "now out of RAM (to the standby list or the page file). The program keeps working, and Windows "
                   "brings the pages back when they are needed again, which can cause a short pause, for example when "
                   "you switch back to an old browser tab.\n\nSoft limit: the limit is for the whole program, all of "
                   "its processes together. When it is exceeded, SimpleTool trims the largest processes first until "
                   "the program is under the limit, and does nothing while the program stays within it.\n\nHard limit: "
                   "Windows caps the RAM of every process of the program. It holds the limit firmly, but a program that "
                   "really needs more memory can become noticeably slower. The caps are removed when you turn the "
                   "limiter off or exit SimpleTool.\n\nSystem processes (Explorer, svchost and others) cannot be "
                   "added: limiting them could freeze Windows.",
        "mem_pick_title": "Running programs",
        "mem_pick_text": "Choose a program to limit. System processes are not shown.",
        "mem_pick_empty": "No other programs are running.",
        "mem_size_mb": "{n} MB",
        "mem_size_gb": "{n} GB",
        "tray_open": "Open SimpleTool",
        "tray_limiter": "Memory limiter",
        "tray_exit": "Exit",
        "tray_tip_on": "SimpleTool: memory limiter is on",
        "tray_tip_off": "SimpleTool: memory limiter is off",
        "tray_hidden_title": "SimpleTool is in the tray",
        "tray_hidden_text": "The memory limiter keeps working. Open or exit SimpleTool from this icon.",
        "busy_wait": "Wait until the current operation finishes, then exit.",
    },
    "themes": {"navy": "Navy", "midnight": "Midnight", "light": "Light"},
    "categories": {
        "overview": ("System overview", "What is on in Windows right now: services related to telemetry, performance and security."),
        "privacy": ("Privacy", "Telemetry, tracking and data sent to Microsoft."),
        "system": ("System", "Startup, input and built-in Windows features."),
        "explorer": ("File Explorer", "How Explorer opens, what it shows and how fast it responds."),
        "context": ("Context menu", "Useful right-click items. On Windows 11 they are under “Show more options”."),
        "snapshots": ("System snapshots", "How things were before: SimpleTool saves the state before every change, "
                                          "and you can go back to any snapshot."),
        "memory": ("Memory limiter", "Keeps Chrome, Discord and other programs from taking too much RAM."),
    },
    "tweaks": {
        "ads": (
            "Turn off advertising ID",
            "Apps can no longer use your advertising ID to show personalised ads.",
            "Windows gives every user an advertising ID, a unique number that Microsoft Store apps and some Windows "
            "features use to pick ads and track how you respond to them across apps. This tweak turns the ID off for "
            "your account, the same switch as Settings → Privacy → General. You will still see ads, but they are no "
            "longer tailored to you by this ID. Nothing else in Windows depends on it."),
        "sync": (
            "Turn off settings sync",
            "Windows stops syncing themes, passwords, language and other settings with your Microsoft account.",
            "When you sign in with a Microsoft account, Windows uploads your theme, saved passwords, language "
            "preferences, accessibility options, browser and other settings to the cloud and applies them on your "
            "other PCs. This tweak turns off every sync group for your account. Your settings stay on this PC; they "
            "just stop being copied to the cloud and from other devices."),
        "telemetry": (
            "Turn off Windows telemetry",
            "Disables the DiagTrack service and its logger, the WAP push service and Office telemetry tasks.",
            "The Connected User Experiences and Telemetry service (DiagTrack) collects diagnostic and usage data and "
            "sends it to Microsoft, and the Diagtrack-Listener logger records events for it from the moment Windows "
            "starts. The WAP Push service (dmwappushservice) delivers device management messages and feeds the same "
            "pipeline. This tweak stops the logger, sets both services to Disabled and stops them, and disables "
            "Office telemetry tasks if Office is installed. Windows Update, the Store and Defender keep working. The "
            "WAP Push service is also used to enrol a PC in company device management (Intune or another MDM), so "
            "do not use this tweak on a work PC managed by your organisation."),
        "nvidia": (
            "Turn off NVIDIA telemetry",
            "Disables the NVIDIA telemetry service and its scheduled tasks, if they are installed.",
            "Older NVIDIA drivers install the NvTelemetryContainer service and three scheduled tasks (NvTmRep, "
            "NvTmRepOnLogon, NvTmMon) that report driver usage to NVIDIA. This tweak disables and stops the service "
            "and turns the tasks off. Games, the NVIDIA Control Panel and driver updates are not affected. Newer "
            "drivers no longer ship this service; if none of these parts exist on your PC, the tweak shows Not found."),
        "data_tasks": (
            "Turn off data collection tasks",
            "Disables scheduled tasks that gather compatibility, CEIP, disk diagnostics and network data for Microsoft.",
            "Windows regularly runs maintenance tasks that collect data for Microsoft: the Compatibility Appraiser "
            "and ProgramDataUpdater inventory your apps before upgrades, the Customer Experience Improvement Program "
            "(CEIP) tasks send usage statistics, disk diagnostics report drive health, and other tasks gather network "
            "and performance information. This tweak disables those tasks in Task Scheduler. They run in the "
            "background, so you will not notice them missing; upgrade compatibility checks and the Startup impact "
            "column in Task Manager may become less informative. Tasks that do not exist on your version of Windows "
            "are skipped."),
        "inventory": (
            "Turn off app inventory",
            "Windows stops collecting the list of installed programs and sending it to Microsoft.",
            "The Inventory Collector builds a list of the programs, drivers and files installed on your PC and sends "
            "it to Microsoft as part of compatibility telemetry. This tweak turns on the “Turn off Inventory "
            "Collector” policy. Programs keep working; the Program Compatibility Assistant may offer fewer fixes for "
            "old software."),
        "diagnostics": (
            "Minimise diagnostic data",
            "Sets diagnostic data to the lowest level your edition allows and turns off application telemetry.",
            "Windows sends diagnostic data to Microsoft at the level chosen in Settings → Privacy → Diagnostics & "
            "feedback. This tweak sets the AllowTelemetry policy to 0, the lowest level, and turns off the "
            "Application Telemetry engine, which tracks how you use Windows features in programs. Level 0 (Security) "
            "is honoured only by the Enterprise, Education and Server editions; Home and Pro treat it as Required, "
            "the lowest level they support. Settings may then say “Some settings are managed by your organisation”, "
            "which is normal for policies."),
        "handwriting": (
            "Turn off handwriting data sharing",
            "Stops sending handwriting samples and error reports and turns off typing personalisation.",
            "To improve handwriting recognition, Windows can send samples of your pen input and recognition error "
            "reports to Microsoft and learn from what you type (inking and typing personalisation). This tweak "
            "blocks sharing of handwriting data and error reports with policies and turns typing personalisation off "
            "for your account. Pen and touch input keep working; word suggestions adapt less to your vocabulary."),
        "steps_recorder": (
            "Turn off Steps Recorder and lock screen camera",
            "Disables recording of user actions and blocks the camera on the lock screen.",
            "Steps Recorder (psr.exe) records every click and keystroke with screenshots, which helps tech support "
            "but captures everything you do on screen. This tweak turns it off with the “Turn off Steps Recorder” "
            "policy and blocks the camera on the lock screen, so nobody can take photos before signing in. If you "
            "send Steps Recorder captures to tech support, leave this tweak off."),
        "location": (
            "Turn off location",
            "Turns off location for the whole system: maps, weather and Find my device will not see where you are.",
            "Windows location services let apps and Windows features find out where your PC is, using GPS, Wi-Fi "
            "and the IP address. This tweak turns location off for the whole system with policies, including "
            "location scripting and the Windows location provider. Maps, weather and Find my device no longer get "
            "your location, and the automatic time zone may stop updating when you travel. Revert turns it back on."),
        "feedback": (
            "Turn off feedback requests",
            "Windows stops asking for feedback and stops counting how often you send it.",
            "Windows periodically asks for feedback in notifications and through the Feedback Hub, and keeps count "
            "of how often you were asked. This tweak sets the feedback frequency to never and hides feedback "
            "notifications with a policy. You can still open the Feedback Hub yourself."),
        "speech": (
            "Turn off speech model updates",
            "Stops background downloads of speech recognition and synthesis model updates.",
            "Windows downloads updated speech recognition and text-to-speech models in the background, even if you "
            "never use voice features. This tweak blocks those updates with a policy. Voice typing, Narrator and "
            "other speech features keep working with the models that are already installed."),
        "experiments": (
            "Turn off Microsoft experiments",
            "Prevents Microsoft from remotely turning on experimental features on this PC.",
            "Microsoft can turn on features that are still being tested on some PCs to try them before release; the "
            "AllowExperimentation setting controls this. This tweak sets it to 0, so no experiments run on this PC. "
            "Regular updates and features released to everyone are not affected."),
        "startup_delay": (
            "Remove startup delay",
            "Startup programs launch right after sign-in instead of waiting several seconds.",
            "After you sign in, Explorer waits several seconds before it starts programs from the Startup folder and "
            "the Run registry keys, so the desktop appears sooner. This tweak removes that wait. On a fast SSD "
            "everything starts earlier; on a slow hard drive, many programs starting at once can make the first "
            "minute after sign-in feel slower."),
        "autoplay": (
            "Turn off AutoPlay",
            "USB drives and discs no longer open or run anything on their own when connected.",
            "AutoPlay opens a window or starts an action as soon as you connect a USB drive, memory card, phone or "
            "disc. Malicious USB drives have used this to start programs automatically. This tweak turns AutoPlay off "
            "for all media and devices for your account; you open them yourself from File Explorer."),
        "layout_hotkey": (
            "Switch keyboard layout with Ctrl+Shift",
            "Changes the input language shortcut from Alt+Shift to Ctrl+Shift.",
            "By default Alt+Shift switches the input language and Ctrl+Shift switches the keyboard layout within a "
            "language. This tweak makes Ctrl+Shift switch the input language and removes the separate layout "
            "shortcut. Win+Space keeps working. The change takes effect after you sign out or restart."),
        "photo_viewer": (
            "Restore Windows Photo Viewer",
            "Adds the classic Photo Viewer to “Open with” for JPG, PNG, GIF, BMP and other images.",
            "Windows Photo Viewer is still part of Windows 10 and 11, but it is hidden and opens only TIFF files. "
            "This tweak registers it for JPG, PNG, GIF, BMP, ICO and other image types. Then right-click an image, "
            "choose Open with → Choose another app and pick Windows Photo Viewer; tick “Always use this app” to make "
            "it the default. The Photos app is not removed."),
        "lock_timeout": (
            "Unlock lock screen timeout setting",
            "Adds the lock screen display timeout to Power Options, so the screen no longer goes dark after one minute.",
            "On the lock screen Windows turns the display off after one minute, whatever your power settings say. "
            "The “Console lock display off timeout” option controls this, but it is hidden. This tweak shows it in "
            "Control Panel → Power Options → Change advanced power settings → Display, where you can set your own "
            "timeout. The tweak itself does not change the timeout."),
        "desktop_shortcuts": (
            "Restart and Refresh icons shortcuts",
            "Creates two desktop shortcuts: restart the PC and refresh the icon cache.",
            "Creates two shortcuts on your desktop. Restart restarts the PC immediately, without asking, so save your "
            "work first; programs with unsaved changes can still stop the restart. Refresh icons runs ie4uinit.exe "
            "-show, which rebuilds the icon cache and redraws the desktop; it helps when icons look wrong after "
            "installing or removing programs. Revert deletes both shortcuts."),
        "file_extensions": (
            "Show file extensions",
            "Always shows .exe, .pdf, .jpg and other extensions, so a disguised file is easier to spot.",
            "By default File Explorer hides the extensions of known file types, so “invoice.pdf.exe” looks like "
            "“invoice.pdf”. Attackers rely on this to disguise programs as documents. This tweak shows extensions for "
            "all files. Be careful when renaming: if you change the extension, the file may open in another program."),
        "open_this_pc": (
            "Open This PC with Win+E",
            "File Explorer opens on This PC with your drives instead of Home or Quick access.",
            "Win+E and the File Explorer icon open Home (Quick access on Windows 10) with recent files. This tweak "
            "makes them open This PC with your drives and folders. Recent files are still one click away in the "
            "navigation pane."),
        "empty_drives": (
            "Show empty drives",
            "Card readers and other drives without media stay visible in This PC.",
            "File Explorer hides drives without media, such as a card reader with no card or an empty DVD drive. "
            "This tweak always shows them, so every drive letter is visible and you do not have to wonder where the "
            "card reader went."),
        "long_paths": (
            "Allow long file paths",
            "Removes the 260-character path limit for programs that support long paths.",
            "By default a file path in Windows is limited to 260 characters, which breaks deep folders such as "
            "Node.js projects or archives with long names. This tweak turns on long path support for the whole "
            "system. Only programs that support it benefit (PowerShell, Python, Git, modern .NET apps); classic "
            "File Explorer dialogs and older programs keep the limit."),
        "restore_folders": (
            "Reopen folders after sign-in",
            "Folder windows that were open before you signed out or restarted open again.",
            "When you restart or sign out, open File Explorer windows are closed and lost. This tweak makes Windows "
            "reopen the folder windows that were open, in the same places, the next time you sign in."),
        "recent_history": (
            "Turn off recent files history",
            "Quick access, Start and Run stop showing recent and frequent files and programs.",
            "Windows remembers the files and folders you open and the programs you start, and shows them in Quick "
            "access, in Start (Recommended, jump lists) and in the Run dialog. This tweak stops tracking documents "
            "and programs and hides recent and frequent items in Quick access. History collected so far is no longer "
            "shown. Pinned items are not affected."),
        "menu_delay": (
            "Faster menus",
            "Submenus open instantly instead of after a 0.4-second delay.",
            "Windows waits 400 ms before it opens a submenu under the pointer, for example Open with or Send to in "
            "the context menu. This tweak cuts the delay to 20 ms, so menus open immediately. It takes effect after "
            "you sign out or restart."),
        "take_ownership": (
            "Take ownership",
            "Shift + right-click a file or folder to give Administrators full access to it. Be careful with system files.",
            "System files and folders often belong to TrustedInstaller, so even administrators get “Access denied” "
            "when they try to change or delete them. This tweak adds Take ownership to the menu you get with Shift + "
            "right-click on files and folders. After a UAC prompt it makes the Administrators group the owner and "
            "gives it full control, including everything inside a folder. Changing permissions of Windows system "
            "files can break Windows or its updates, so use it on your own data and only when you know why access "
            "is denied."),
        "firewall": (
            "Block or allow internet access",
            "Shift + right-click an .exe to add or remove Windows Firewall rules that block it.",
            "Adds two items to the Shift + right-click menu of .exe files. Block internet access creates Windows "
            "Defender Firewall rules that block the program's inbound and outbound connections; Allow internet "
            "access deletes those rules. Both need administrator rights (a UAC prompt). The rules are named "
            "“SimpleTool - <path>”, so you can find them in wf.msc. Useful for programs that should work offline, "
            "for example to stop them updating."),
        "cmd_desktop": (
            "Command Prompt on the desktop",
            "Right-click the desktop to open Command Prompt in the Desktop folder.",
            "Adds Command Prompt to the menu you get when you right-click an empty spot on the desktop. It opens "
            "cmd.exe in the Desktop folder without administrator rights. On Windows 11 the item is under “Show more "
            "options”."),
        "file_hash": (
            "Get file hash",
            "Copies a file's MD5, SHA1, SHA256, SHA384 or SHA512 checksum to the clipboard.",
            "Adds a Get hash submenu to every file. Pick an algorithm (MD5, SHA1, SHA256, SHA384 or SHA512) and the "
            "checksum is copied to the clipboard in lowercase. Compare it with the checksum on the download page to "
            "make sure the file is complete and has not been tampered with. It uses PowerShell's Get-FileHash, so "
            "large files take a few seconds."),
        "copy_image": (
            "Copy image",
            "Copies the picture itself, not the file, so you can paste it straight into a chat or document.",
            "Adds Copy image to BMP, GIF, ICO, JPEG, PNG and TIFF files. Ctrl+C on a file normally copies the file "
            "itself, which many chats and editors cannot paste as a picture. This item copies the image content, so "
            "you can paste it straight into a chat, a document or a graphics editor."),
        "new_files": (
            "Batch and .reg files in New",
            "Adds Windows Command Script (.cmd) and Registration Entries (.reg) to the New menu.",
            "Adds Windows Command Script (.cmd) and Registration Entries (.reg) to the New menu in File Explorer, so "
            "you can create an empty batch file or registry file right in the current folder. It changes the menu "
            "for every user of the PC, so it needs administrator rights."),
        "hidden_items": (
            "Hidden items toggle",
            "Right-click a folder or its background to show or hide hidden files in one click.",
            "Adds Windows' own Hidden items command to the right-click menu of folders and of the empty area inside "
            "a folder. It shows or hides hidden files and folders in one click, the same as View → Show → Hidden "
            "items. Protected operating system files stay hidden."),
        "notepad": (
            "Open unknown files and .nfo in Notepad",
            "Adds Edit with Notepad for files without an associated program and opens .nfo files as text.",
            "Files without an associated program bring up the “How do you want to open this file?” dialog. This "
            "tweak adds Edit to their right-click menu, which opens them in Notepad. It also makes .nfo files (text "
            "notes that come with downloads) open in Notepad instead of System Information, which cannot read them."),
        "this_pc_tools": (
            "Tools in the This PC menu",
            "Right-click This PC for Control Panel, Device Manager, Services, Disk Management, Registry Editor, "
            "Programs and Features, and restarts into Safe Mode.",
            "Adds frequently needed tools to the right-click menu of This PC: Control Panel, Device Manager, "
            "Services, Disk Management, Registry Editor and Programs and Features. The Safe Mode submenu sets the "
            "next startup mode with bcdedit and restarts the PC: Safe Mode, with networking or with Command Prompt; "
            "Restart normally leaves Safe Mode. The PC restarts right after the UAC prompt, so save your work first. "
            "On Windows 11 the items are under “Show more options”."),
    },
    "menu": {
        "take_ownership": "Take ownership",
        "firewall_block": "Block internet access",
        "firewall_allow": "Allow internet access",
        "cmd": "Command Prompt",
        "hash": "Get hash",
        "hash_copy": "Copy {}",
        "copy_image": "Copy image",
        "control_panel": "Control Panel",
        "device_manager": "Device Manager",
        "services": "Services",
        "disk_management": "Disk Management",
        "registry_editor": "Registry Editor",
        "programs": "Programs and Features",
        "safe_mode": "Safe Mode",
        "restart_normal": "Restart normally",
        "restart_safe": "Restart in Safe Mode",
        "restart_network": "Restart in Safe Mode with Networking",
        "shortcut_restart": "Restart",
        "shortcut_refresh": "Refresh icons",
    },
    "groups": {
        "telemetry": "Telemetry and data collection",
        "location": "Location and maps",
        "performance": "Performance and features",
        "gaming": "Xbox and games",
        "security": "Security and core services",
    },
    "services": {
        "DiagTrack": ("Connected User Experiences and Telemetry",
                      "Collects diagnostic and usage data and sends it to Microsoft. Windows works without it; "
                      "Windows Update and the Store do not depend on it. The Turn off Windows telemetry tweak disables it."),
        "dmwappushservice": ("Device Management WAP Push",
                             "Delivers device management (MDM) messages and is part of the telemetry pipeline. Safe to "
                             "disable on a home PC; needed if your organisation manages the PC with Intune or another MDM."),
        "diagnosticshub.standardcollector.service": (
            "Microsoft Diagnostics Hub Standard Collector",
            "Collects real-time event traces for the Visual Studio and Windows diagnostic tools. Not needed unless "
            "you profile apps in Visual Studio."),
        "WerSvc": ("Windows Error Reporting",
                   "Sends crash and hang reports to Microsoft and offers solutions. When it is off, crashes are not "
                   "reported, Windows cannot suggest fixes and local crash dumps may not be collected."),
        "PcaSvc": ("Program Compatibility Assistant",
                   "Watches programs for known compatibility problems and offers fixes for old software; it also "
                   "reports what you install. Safe to turn off on a modern PC, but those prompts disappear."),
        "NvTelemetryContainer": ("NVIDIA Telemetry Container",
                                 "Reports NVIDIA driver usage. Not needed for games or the driver. Newer drivers no "
                                 "longer install it."),
        "wisvc": ("Windows Insider Service",
                  "Needed only for the Windows Insider Program (preview builds). Starts manually and stays idle on most PCs."),
        "RetailDemo": ("Retail Demo Service",
                       "Runs the demo mode of display PCs in shops. Not used on normal PCs."),
        "lfsvc": ("Geolocation Service",
                  "Finds the PC's location for apps and Windows features. When it is off, maps, weather and the "
                  "automatic time zone cannot see where you are. The Turn off location tweak blocks location with "
                  "policies and leaves the service alone."),
        "MapsBroker": ("Downloaded Maps Manager",
                       "Manages offline maps for the Maps app. Needed only if you use offline maps."),
        "SysMain": ("SysMain (Superfetch)",
                    "Learns which programs you use and preloads them into memory so they start faster. Useful on hard "
                    "drives; on SSDs the gain is small. Turning it off reduces disk activity on slow PCs but makes "
                    "programs start slower."),
        "WSearch": ("Windows Search",
                    "Indexes files, e-mail and other content so search in Start, File Explorer and Outlook is fast. "
                    "Without it search still works, but much slower and finds less."),
        "Spooler": ("Print Spooler",
                    "Manages printing and printer drivers. Without it you cannot print or use Print to PDF. If you "
                    "never print, turning it off also closes a frequently attacked service."),
        "Fax": ("Fax", "Sends and receives faxes through a fax modem. Almost no PC needs it."),
        "XblAuthManager": ("Xbox Live Auth Manager",
                           "Signs in to Xbox services for games and the Xbox app. Needed for Game Pass, achievements "
                           "and multiplayer in Microsoft Store games."),
        "XblGameSave": ("Xbox Live Game Save",
                        "Syncs game saves with Xbox cloud storage. Needed if you play Xbox or Game Pass games on "
                        "several devices."),
        "XboxNetApiSvc": ("Xbox Live Networking Service",
                          "Provides Xbox Live multiplayer connectivity (network checks, NAT). Needed for online play "
                          "in Xbox and Game Pass games."),
        "XboxGipSvc": ("Xbox Accessory Management Service",
                       "Manages Xbox controllers and accessories connected by USB or the wireless adapter (firmware, "
                       "settings). Needed if you use an Xbox controller."),
        "WinDefend": ("Microsoft Defender Antivirus Service",
                      "Real-time protection against malware. It should be running unless another antivirus is "
                      "installed, which turns Defender off by itself. SimpleTool does not change it."),
        "mpssvc": ("Windows Defender Firewall",
                   "Filters network connections. Keep it running: without it firewall rules do not work, including "
                   "the ones created by Block internet access."),
        "wuauserv": ("Windows Update",
                     "Downloads and installs Windows updates. Usually starts manually when needed. Turning it off "
                     "leaves the PC without security updates."),
        "RemoteRegistry": ("Remote Registry",
                           "Lets other computers on the network read and change this PC's registry. Off by default on "
                           "Windows 10 and 11; keep it off unless an administrator needs it."),
        "Schedule": ("Task Scheduler",
                     "Runs scheduled tasks for Windows and programs; SimpleTool reads the task list through it. It "
                     "cannot be turned off the usual way, and many Windows features break when it is not running."),
        "EventLog": ("Windows Event Log",
                     "Records system and program events used for troubleshooting. Keep it running: other services "
                     "depend on it, and Windows cannot be diagnosed without it."),
    },
    "reasons": {
        "access_denied": ("Not enough rights to read some settings.",
                          "Restart SimpleTool as administrator."),
        "scm_unavailable": ("Could not connect to the Windows service manager.",
                            "Restart the PC. If it happens again, check that your antivirus or a group policy does "
                            "not block access to services."),
        "tasks_unavailable": ("Could not read the list of scheduled tasks.",
                              "Open services.msc and check that Task Scheduler is running, and make sure PowerShell "
                              "is not blocked by a policy or antivirus. Then press Scan again."),
        "error": ("An unexpected error occurred while reading.",
                  "Press Scan again. If it repeats, restart the PC and run SimpleTool as administrator."),
    },
}

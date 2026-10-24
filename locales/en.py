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
        "done_apply": "Applied: {n}.{after}",
        "done_revert": "Reverted: {n}.{after}",
        "after_explorer": " Explorer was restarted, so the change shows at once.",
        "after_signout": " Sign out and back in for the change to take effect.",
        "after_restart": " Restart the PC for the change to take effect.",
        "explorer_restart_failed": "Explorer could not be restarted; sign out and back in instead.",
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
        "diag_scan_title": "Looking for problems",
        "diag_scan_text": "SimpleTool checks memory, the processor, drives, drivers, the Windows event logs and settings. "
                          "It only reads, and it takes a few seconds.",
        "diag_step_performance": "Memory, processor and startup",
        "diag_step_storage": "Drives and free space",
        "diag_step_stability": "Crashes, drivers and hardware errors",
        "diag_step_security": "Protection, updates and network",
        "diag_tile_problem": "Problems",
        "diag_tile_warning": "Warnings",
        "diag_tile_info": "Worth knowing",
        "diag_tile_ok": "All good",
        "diag_checked": "Checked at {time}. SimpleTool only read the system and changed nothing.",
        "diag_sec_attention": "Needs attention",
        "diag_sec_info": "Worth knowing",
        "diag_sec_ok": "All good",
        "diag_sec_unknown": "Could not check",
        "diag_problem": "Problem",
        "diag_warning": "Warning",
        "diag_info": "Note",
        "diag_ok": "OK",
        "diag_unknown": "Not checked",
        "diag_clear_title": "Nothing needs attention",
        "diag_clear_text": "SimpleTool found no problems. If the PC still slows down or crashes, run the check again right "
                           "after it happens: the logs then show what went wrong.",
        "diag_running": "Looking for problems…",
        "diag_footer": "Troubleshooting only reads the system. Open Details to see what a finding means and how to fix it.",
        "diag_open_failed": "Windows could not open it on this PC.",
        "act_memory": "Memory limiter",
        "act_taskmgr": "Task Manager",
        "act_virtual_memory": "Virtual memory",
        "act_power": "Power plans",
        "act_power_mode": "Power settings",
        "act_display": "Display settings",
        "act_startup": "Startup apps",
        "act_captures": "Capture settings",
        "act_storage": "Storage settings",
        "act_temp": "Open the folder",
        "act_events": "Event Viewer",
        "act_reliability": "Reliability Monitor",
        "act_devices": "Device Manager",
        "act_security": "Windows Security",
        "act_update": "Windows Update",
        "act_proxy": "Proxy settings",
        "act_hosts": "Open the hosts file",
        "act_system_config": "System Configuration",
        "act_services": "Services",
        "act_core_isolation": "Core isolation",
        "act_graphics_settings": "Graphics settings",
        "act_network_status": "Network status",
        "act_optional_features": "Optional features",
        "act_recovery": "Recovery",
        "act_uac": "UAC settings",
    },
    "themes": {"navy": "Navy", "midnight": "Midnight", "light": "Light"},
    "categories": {
        "overview": ("System overview", "What is on in Windows right now: services related to telemetry, performance and security."),
        "diagnostics": ("Troubleshooting", "Looks for what makes Windows slow or unstable: memory, drives, drivers, crashes and conflicting settings. It only reads and changes nothing."),
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
        "registry_backup": (
            "Automatic registry backup",
            "Windows keeps a copy of the registry in RegBack again, for repairs when it does not start.",
            "Up to Windows 10 version 1803, Windows kept a copy of the registry in "
            "C:\\Windows\\System32\\config\\RegBack, refreshed by the RegIdleBackup task during automatic maintenance, "
            "and a damaged registry could be repaired from that copy in the recovery environment. Since then the task "
            "runs but saves nothing, to save disk space. This tweak turns the copies back on with the value Microsoft "
            "documents for it; the first copy is made after a restart, and the task refreshes it from then on. It "
            "does not replace restore points, and SimpleTool still asks for one before applying."),
        "verbose_status": (
            "Detailed sign-in and shutdown messages",
            "Windows says what it is doing while you sign in, sign out and shut down.",
            "Instead of a plain Welcome or Shutting down, Windows shows each step: applying your settings, starting "
            "services, running sign-in scripts, waiting for programs to close. When sign-in or shutdown takes long, "
            "the step that stays on the screen tells you what is slow. This is the Windows policy “Display highly "
            "detailed status messages”, which administrators use for exactly that; it changes nothing else. The "
            "messages appear from the next sign-in."),
        "store_open_with": (
            "No Microsoft Store in “Open with”",
            "Opening a file of an unknown type does not offer to look for an app in the Microsoft Store.",
            "When no program is set for a file type, Windows asks how to open the file and offers to look for an app "
            "in the Microsoft Store. That line is easy to click by mistake and often leads to paid or unrelated apps. "
            "This tweak removes it from the dialog with the Windows policy made for that; the programs on this PC and "
            "“Look for another app on this PC” stay. The Store itself keeps working."),
        "spotlight_icon": (
            "No “Learn about this picture” icon",
            "Removes the Windows Spotlight icon from the desktop; the changing wallpapers stay.",
            "With Windows Spotlight as the desktop background, Windows 11 puts a “Learn about this picture” icon on "
            "the desktop, and Delete does not remove it. This tweak hides it the way Windows hides the Recycle Bin or "
            "This PC: with a value in the desktop icon settings. The pictures keep changing, nothing else is touched, "
            "and the icon comes back when you revert. If the desktop does not refresh at once, click on it and press "
            "F5."),
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
        "classic_menu": (
            "Classic right-click menu",
            "Windows 11 shows the full menu at once, with no “Show more options”.",
            "Windows 11 opens a short menu first and keeps the rest, including the items SimpleTool adds, behind "
            "“Show more options” (Shift+F10). This tweak brings back the full Windows 10 style menu for your account: "
            "the registry entry of the new menu’s component is overridden with an empty one, so Explorer loads the "
            "classic menu. SimpleTool restarts Explorer after applying or reverting, so open folder windows close for "
            "a moment. Not needed on Windows 10, where the menu is already like that."),
        "copy_move_to": (
            "Copy to folder and Move to folder",
            "Right-click a file or folder to copy or move it to a folder you pick from a tree.",
            "Adds two classic Windows commands to the right-click menu of files and folders. “Copy to folder…” and "
            "“Move to folder…” open a small window with the folder tree, you pick the destination, and Windows copies "
            "or moves the selection there, without a second Explorer window. The commands are Windows’ own shell "
            "extensions, which only ever needed to be switched on in the registry, so they come in your language. On "
            "Windows 11 they are under “Show more options”, unless the classic menu tweak is on."),
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
    "diag": {
        "ram_load": ("Memory use",
                     "How much of the RAM is in use right now. Above 80–90% Windows starts moving memory out to the page "
                     "file on the drive, and programs stutter, switch slowly and reload browser tabs. Close what you do "
                     "not need: the list shows the programs that take the most. Browsers, Discord and similar programs "
                     "can be kept within a limit on the Memory limiter page."),
        "ram_size": ("Installed memory",
                     "How much RAM Windows can use. Windows 10 and 11 with a browser and a few programs need about 8 GB "
                     "to run smoothly; with 4 GB or less the PC uses the page file all the time and slows down. Windows "
                     "reports a little less than is installed, because part of it is reserved for the graphics and the "
                     "firmware. The only real fix is more memory."),
        "pagefile": ("Page file",
                     "The page file is where Windows keeps memory that is not needed right now, and it sets how much "
                     "memory programs may take in total (the commit limit). When it is off or the limit is almost used "
                     "up, programs crash with out-of-memory errors and some games do not start, even when RAM looks "
                     "free. Keep the page file on and let Windows choose its size: Virtual memory → Automatically "
                     "manage paging file size for all drives. "
                     "When memory runs out, Windows writes a warning to its log with the programs that took the "
                     "most: the list shows them. "
                     "A page file limited to a small fixed size, or set on a drive that is gone or full, leads to "
                     "the same out-of-memory crashes."),
        "cpu_load": ("Processor load",
                     "How busy the processor was during the second SimpleTool measured it. A constant load above 80% "
                     "while nothing heavy is running means a program works in the background: the list shows which. "
                     "Check a program you do not know with your antivirus. Updates and indexing keep the processor "
                     "busy for a while after the PC starts, so check again in a few minutes."),
        "power_plan": ("Power plan",
                       "The Power saver plan and the Windows 11 power mode “Best power efficiency” hold the processor "
                       "at lower speeds. That saves the battery of a laptop, but on a plugged-in PC everything gets "
                       "slower, games most of all. Choose the Balanced or High performance plan, and on Windows 11 the "
                       "Balanced or Best performance power mode. "
                       "The same happens when the plan turns turbo boost off or caps the processor's frequency or "
                       "maximum state."),
        "refresh_rate": ("Display refresh rate",
                         "How many times a second each display draws a new picture. Many monitors support 120 or "
                         "144 Hz and more but run at 60 Hz after a driver update or with the wrong cable: motion is "
                         "less smooth and games feel slower. Choose the highest rate in Display settings → Advanced "
                         "display. If it is not offered, use a DisplayPort or high-speed HDMI cable and update the "
                         "graphics driver."),
        "startup_apps": ("Startup programs",
                         "Programs that start by themselves when you sign in to Windows. Each one makes the start "
                         "slower and keeps using memory and the processor in the background. More than ten is a lot: "
                         "turn off the ones you do not need right away in Startup apps. They still work when you open "
                         "them yourself."),
        "game_dvr": ("Background game recording",
                     "Xbox Game Bar can record the last minutes of every game all the time, so that a clip can be saved "
                     "afterwards. The constant recording takes graphics and drive resources and lowers FPS, especially "
                     "on weaker PCs. If you do not save clips this way, turn off Record what happened in the capture "
                     "settings."),
        "uptime": ("Time since restart",
                   "How long Windows has run without a restart. Over days and weeks memory leaks in drivers and programs "
                   "add up and updates wait to be finished, so the PC gets slower. Restart it at least once a week. With "
                   "Fast startup on, Shut down only hibernates Windows and does not count: use Restart."),
        "disk_space": ("Free space",
                       "Windows needs free space on its own drive for updates, the page file, temporary files and "
                       "restore points. With less than about 20 GB free, updates fail and the PC slows down; below "
                       "5 GB programs can stop working. Free up space in Storage settings: Temporary files and Cleanup "
                       "recommendations show what can be removed safely."),
        "disk_health": ("Drive health",
                        "What the drives report about themselves (S.M.A.R.T. and their own checks). Warning or "
                        "failing means the drive is wearing out or breaking down: it can stop working at any moment and "
                        "take your files with it. Copy your important files somewhere else now, then replace the "
                        "drive. "
                        "Run as administrator, SimpleTool also reads how worn each SSD is: at 100% it has reached "
                        "the wear its maker rates it for."),
        "system_drive": ("Windows drive",
                         "The type of drive Windows is on. A hard disk (HDD) is many times slower than an SSD at the "
                         "small reads Windows does all the time: a slow start, freezes when programs open and the disk "
                         "at 100% in Task Manager. Moving Windows to an SSD is the upgrade that helps such a PC most. "
                         "On an SSD TRIM must stay on: without it the drive gets slower as it fills up. Turn it back "
                         "on with “fsutil behavior set DisableDeleteNotify 0” as administrator. "
                         "Windows on eMMC flash, a memory card or a USB drive is slow at everything."),
        "disk_errors": ("Drive errors",
                        "Errors that the drives and the file system recorded in the Windows log over the last 30 days. "
                        "Bad blocks, paging and controller errors and file system damage are signs of a failing drive "
                        "or a bad cable: back up your files and test the drive with its maker's tool. Retries and "
                        "resets on their own often come from power saving or a loose cable and cause short freezes. "
                        "Errors from memory sticks and cards that were pulled out are normal and only noted."),
        "temp_files": ("Temporary files",
                       "The size of your temporary folder (%TEMP%). Programs leave installers, caches and logs there "
                       "and often do not clean them up. A few gigabytes are normal; more only takes space. Delete them "
                       "in Storage settings → Temporary files, or open the folder and delete what is there: files in "
                       "use are skipped."),
        "crashes": ("Blue screens and sudden shutdowns",
                    "A blue screen (a stop error) means Windows hit a fault it could not recover from, most often in a "
                    "driver or in the hardware. A sudden shutdown means the PC turned off or restarted without shutting "
                    "down: a power cut, holding the power button, overheating or a power supply problem. Reliability "
                    "Monitor shows every event and what came before it; the stop code helps to find the cause. "
                    "When Windows hangs while shutting down and the PC is then turned off, it also counts as turned "
                    "off without shutting down: the list says when that happened. A driver or program that does not "
                    "let Windows finish is the usual cause."),
        "app_crashes": ("Program crashes",
                        "Programs that closed with an error or stopped responding over the last 14 days, according to "
                        "the Windows log. One program crashing again and again usually needs an update or a reinstall; "
                        "many different programs crashing point to a common cause: memory, a driver or an overlay. "
                        "Reliability Monitor shows the details of every crash. "
                        "The list also names the module a program crashed in: an overlay (Discord, Steam, RivaTuner, "
                        "OBS), the graphics driver, or Windows' own code."),
        "gpu_resets": ("Graphics driver crashes",
                       "Windows restarts the graphics driver when it stops responding for a few seconds: the screen "
                       "goes black or freezes, and a game may close. The NVIDIA driver also records its own errors, "
                       "and Windows reports graphics engines that stopped responding. The usual causes are an old or "
                       "damaged driver, overclocking, an overheating graphics card or a weak power supply. Install "
                       "the latest driver from the maker of the graphics card (NVIDIA, AMD or Intel); if it goes on, "
                       "check the temperatures, remove the overclock and check the card's power cables."),
        "whea": ("Hardware errors",
                 "Errors that the processor, the memory or the PCI Express bus reported to Windows (WHEA). A fatal "
                 "error usually ends in a blue screen. Corrected errors do not stop the PC, but many of them point to "
                 "unstable overclocking or memory (XMP/EXPO) settings, a failing part or an outdated BIOS. The details "
                 "are in Event Viewer → Windows Logs → System, source WHEA-Logger. "
                 "Corrected processor and memory errors are a warning sign even when there are few."),
        "devices": ("Devices",
                    "Devices that Windows marks with a warning in Device Manager: no driver, a driver that does not "
                    "start, or a device that reported a problem. A resource conflict (code 12) means two devices want "
                    "the same resource. Install the driver from the device's maker, or uninstall the device in Device "
                    "Manager and restart the PC so that Windows sets it up again."),
        "battery": ("Battery wear",
                    "How much charge the battery holds compared with when it was new. Every battery wears out; below "
                    "60% the laptop runs noticeably shorter on battery, and below 40% it may turn off suddenly under "
                    "load. The only fix is a new battery."),
        "antivirus": ("Antivirus",
                      "Which antiviruses Windows Security Center sees. Without real-time protection the PC is open to "
                      "malware. Two active antiviruses at once conflict: they scan the same files twice, slow the PC "
                      "down and can make each other crash. Keep one. When you install another antivirus, Microsoft "
                      "Defender turns itself off, and that is normal."),
        "windows_update": ("Windows Update",
                           "When Windows last installed updates. Updates close security holes and fix bugs, driver "
                           "problems included. If the service is disabled or a policy turns updates off (other "
                           "optimization tools often leave this behind), Windows stops getting fixes. Open Windows "
                           "Update and install what it offers. "
                           "An update that keeps failing is listed with its error code, which Microsoft's support "
                           "site explains."),
        "pending_restart": ("Restart pending",
                            "Windows has installed updates that are finished only after a restart. Until then old and "
                            "new files live side by side, which can cause errors and slow the PC down, and new updates "
                            "may wait. Save your work and restart the PC."),
        "windows_support": ("Windows version",
                            "Microsoft supports each version of Windows for a limited time; after that it gets no "
                            "security updates. Windows Update offers the newest version for free. Windows 10 support "
                            "ended on 14 October 2025: since then only PCs enrolled in Extended Security Updates get "
                            "security fixes, home PCs until 12 October 2027."),
        "proxy": ("Proxy server",
                  "A proxy server is set for this account: browsers and many programs send their internet traffic "
                  "through it. A VPN or an antivirus may set one on purpose, but a proxy you do not know about can be "
                  "left by malware or by a program removed long ago, and it causes errors and slow internet. If you "
                  "did not set it, turn it off in Proxy settings."),
        "hosts": ("Hosts file",
                  "The hosts file tells Windows which address to use for a name before the internet is asked. Blocking "
                  "telemetry there is fine, but blocking addresses Windows itself needs breaks Windows Update, the "
                  "Microsoft Store, activation, sign-in or Xbox. A hosts file with tens of thousands of lines also "
                  "slows down every connection. Edit it as administrator: put # at the start of a line to turn it "
                  "off."),
        "graphics_driver": ("Graphics driver",
                            "Which driver the graphics card works with. Without its own driver Windows runs it on "
                            "the Microsoft Basic Display Adapter: no 3D acceleration, a low resolution and refresh "
                            "rate, slow video and scrolling, and games do not start. A graphics card driver that is "
                            "years old lacks the fixes and optimisations newer games need. Install the latest driver "
                            "from NVIDIA, AMD or Intel, or the one Windows Update offers under Optional updates. "
                            "A graphics card disabled in Device Manager leaves games on the processor's graphics: "
                            "enable it there. NVIDIA drivers older than 581.94 lose a lot of FPS in some games after "
                            "the October 2025 Windows update."),
        "display_output": ("Monitor connection",
                           "Which graphics the monitor is plugged into. A desktop with a graphics card also has "
                           "video outputs on the motherboard, and they belong to the graphics built into the "
                           "processor. A monitor plugged in there gets its picture from the processor: games run "
                           "much slower, or Windows renders them on the card and copies every frame across, which "
                           "costs FPS and adds delay. Plug the monitor cable into the outputs of the graphics card, "
                           "usually lower down on the back of the PC."),
        "boot_options": ("Boot and debugging options",
                         "Settings that limit Windows or switch on modes for developers. The number of processors "
                         "and the maximum memory in System Configuration (msconfig → Boot → Advanced options) do not "
                         "speed anything up, as some guides claim: they make Windows use fewer cores or less memory. "
                         "Test mode lets unsigned drivers load, and anti-cheats such as Riot Vanguard and BattlEye "
                         "refuse to run with it. Kernel debugging is meant for driver developers. Driver Verifier "
                         "slows the PC down and crashes it on purpose to catch a faulty driver. With graphics driver "
                         "recovery turned off, every driver hang becomes a frozen PC or a blue screen. Undo what you "
                         "did not set on purpose: clear the limits in msconfig, run “bcdedit /set testsigning off”, "
                         "“bcdedit /debug off” and “verifier /reset” as administrator, then restart. "
                         "Forcing the HPET timer (useplatformclock) is meant for debugging and can lower FPS: remove "
                         "it with “bcdedit /deletevalue useplatformclock”."),
        "memory_test": ("Memory test",
                        "The result of the last Windows Memory Diagnostic test, if it was run on this PC. Errors "
                        "mean a memory module is faulty or unstable: that causes random crashes, blue screens and "
                        "damaged files. Remove overclocking and XMP/EXPO settings in the BIOS and test again; if "
                        "errors remain, test the modules one by one and replace the faulty one."),
        "services": ("Failing services",
                     "Windows services that failed to start or stopped with an error again and again over the last "
                     "week, according to the Windows log. The feature such a service provides does not work. Often "
                     "it is left over from a program that was removed or updated badly, or another program blocks "
                     "it. Reinstall or update the program it belongs to; for a Windows service run “sfc /scannow” "
                     "and then “DISM /Online /Cleanup-Image /RestoreHealth” as administrator."),
        "memory_integrity": ("Memory integrity",
                             "Memory integrity (core isolation) protects Windows from malicious and vulnerable "
                             "drivers. Microsoft notes that it can lower performance in some games, more so on "
                             "processors without MBEC/GMET, and from October 2026 Windows updates turn it on by "
                             "themselves on PCs that support it. If a game has run worse since, you can turn it off "
                             "in Windows Security → Device security → Core isolation, but the PC loses that "
                             "protection. Otherwise keep it on."),
        "network": ("IP address conflicts",
                    "Windows records when another device on the local network uses the same IP address as this PC. "
                    "Then the connection drops or the internet works only now and then. Usually a device has a fixed "
                    "address that the router also hands out. Restart the router, and give fixed addresses only "
                    "outside the range the router assigns, or let the router assign every address. "
                    "A wired connection at 100 Mb/s instead of a gigabit almost always means a damaged cable or a "
                    "bad port."),
        "memory_config": ("Memory modules",
                          "How the memory modules are installed. With one module the processor reads memory over one "
                          "channel instead of two: games get noticeably fewer frames, and the graphics built into "
                          "the processor suffer most. A kit rated for a higher speed runs at the basic speed until "
                          "XMP or EXPO is turned on in the BIOS. Modules of different kinds run at the speed of the "
                          "slowest and can be unstable. Install memory in pairs from one kit, in the slots the "
                          "motherboard manual names (usually A2 and B2), and turn on XMP/EXPO."),
        "kernel_memory": ("Driver memory",
                          "Memory that Windows' drivers keep for themselves (the non-paged pool). It never moves to "
                          "the page file, so when a driver leaks it, the RAM fills up although no program in Task "
                          "Manager uses it. Usually it is less than a gigabyte. Network, VPN, antivirus, RGB and "
                          "monitoring drivers are the usual culprits: update or remove the one you installed last; a "
                          "restart frees the memory for a while."),
        "cpu_microcode": ("Intel 13th and 14th Gen processor",
                          "Intel's 13th and 14th Gen Core i5, i7 and i9 desktop processors can degrade with the "
                          "voltage their old microcode requests: games crash, files fail to unpack, blue screens "
                          "appear. Intel fixed it with microcode 0x12B in 2024 and released 0x12F in 2025; it "
                          "reaches the processor with a BIOS update from the motherboard maker. Update the BIOS and "
                          "use its Intel Default Settings profile. If the PC already crashes, the processor may have "
                          "degraded: Intel extended the warranty of these processors to five years."),
        "x3d_cores": ("Ryzen X3D cores",
                      "A Ryzen 9 X3D processor has two sets of cores, and only one has the extra 3D V-Cache that "
                      "makes games fast. Windows sends games to those cores through AMD's chipset driver (3D V-Cache "
                      "Performance Optimizer) and the Xbox Game Bar, which recognises games. Without them games may "
                      "land on the other cores and run slower. Install the latest AMD chipset driver, keep the Xbox "
                      "Game Bar installed and Game Mode on."),
        "gpu_link": ("Graphics card slot",
                     "How many PCI Express lanes the graphics card works with. A card built for 16 lanes that gets 4 "
                     "or fewer loses a large share of its speed in games. Usually it sits in a lower slot of the "
                     "motherboard, a riser cable is faulty, or the slot shares its lanes with an M.2 drive. Put the "
                     "card in the top long slot and check in the motherboard manual which M.2 slots take lanes from "
                     "it."),
        "gpu_preference": ("Graphics preference",
                           "In Settings → Display → Graphics each program can be told which graphics to use. A "
                           "program set to Power saving runs on the processor's graphics even when the PC has a "
                           "graphics card, and games run much slower. Set games to High performance or let Windows "
                           "decide."),
        "rgb_software": ("Lighting programs",
                         "Programs that control the lighting of the motherboard, memory and fans talk to the same "
                         "chips. Two of them running at once fight over those chips: the lighting flickers, the PC "
                         "stutters, and some programs crash or lose their settings. Keep one of them, or turn off "
                         "its lighting control, and remove the others from startup."),
        "throttling": ("Processor slowed down",
                       "Windows records when the firmware holds the processor below its normal speed: it is too hot, "
                       "the power supply limits it, or a power limit is set in the BIOS. On a desktop this should be "
                       "rare. Clean the dust out of the cooler and the case, check that the cooler sits firmly and "
                       "its fan spins, and check the power limits in the BIOS."),
        "core_services": ("Disabled services",
                          "Windows services that “debloat” and “optimization” tools turn off. Windows works on "
                          "without them, but what they are for breaks: updates, installing programs, sound, the "
                          "firewall, the clock or Xbox. Set their startup type back to Automatic or Manual in "
                          "Services, as Windows has it, and restart the PC. Services that only take away one feature "
                          "are noted."),
        "system_files": ("System files",
                         "Whether Windows has recorded damage in its own system files (the component store). Damaged "
                         "files cause errors, updates that do not install and features that do not work. Run “DISM "
                         "/Online /Cleanup-Image /RestoreHealth” and then “sfc /scannow” as administrator. If the "
                         "damage cannot be repaired, reinstall Windows over itself and keep your files: on Windows "
                         "11 Settings → System → Recovery → Fix problems using Windows Update."),
        "vc_runtime": ("Visual C++ runtime",
                       "Most programs and games need the Microsoft Visual C++ runtime. Programs built with newer "
                       "versions of Visual Studio crash at start, often without a message, when the runtime in "
                       "Windows is older than 14.40. Install the latest Visual C++ Redistributable for x64 and for "
                       "x86 from Microsoft (aka.ms/vc14/vc_redist.x64.exe and aka.ms/vc14/vc_redist.x86.exe)."),
        "media_pack": ("Media features",
                       "N editions of Windows come without Windows Media components. Without them many games and "
                       "launchers do not start, and videos do not play. Install the Media Feature Pack: Settings → "
                       "System → Optional features → Add an optional feature."),
        "security_settings": ("Security settings",
                              "Protections that some “optimization” guides turn off for a speed they do not give. "
                              "With User Account Control fully off every program runs as administrator, Windows "
                              "Security warns about it, and some apps refuse to start. With the Spectre and Meltdown "
                              "mitigations off, a malicious program can read the memory of other programs. Turn UAC "
                              "back on: set EnableLUA to 1 under "
                              "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System and restart. For "
                              "Spectre and Meltdown delete FeatureSettingsOverride and FeatureSettingsOverrideMask "
                              "under HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Memory Management."),
        "secure_boot": ("Secure Boot and TPM",
                        "Windows 11 and the anti-cheats of some games need UEFI boot, Secure Boot and TPM 2.0: Riot "
                        "Vanguard (Valorant, League of Legends) and the anti-cheats of the latest Battlefield and "
                        "Call of Duty refuse to start without them. All three are turned on in the BIOS: boot mode "
                        "UEFI (if the disk is MBR, convert it with mbr2gpt first), Secure Boot, and fTPM or PTT for "
                        "the TPM."),
    },
    "diag_lines": {
        "unknown_read": "Could not read this on this PC.",
        "ram_ok": "{percent}% of {total} in use",
        "ram_high": "{percent}% of {total} in use: programs are short of memory",
        "ram_size_ok": "{total} available to Windows",
        "ram_size_low": "Only {total} available to Windows",
        "pagefile_ok": "On; {percent}% of the memory limit is in use",
        "pagefile_off": "The page file is turned off",
        "commit_high": "{percent}% of the memory limit is in use: programs may crash",
        "cpu_ok": "{percent}% load",
        "cpu_high": "{percent}% load while SimpleTool was checking",
        "power_ok": "“{name}” is in use",
        "power_saver": "“{name}” slows the PC down while it is plugged in",
        "power_efficiency": "The power mode “Best power efficiency” is on while the PC is plugged in",
        "battery_saver": "Battery saver is on",
        "hz_ok": "Displays run at their highest refresh rate",
        "hz_low": "Display {number} runs at {hz} Hz but supports {max_hz} Hz",
        "startup_ok": "Programs that start with Windows: {n}",
        "startup_many": "Programs that start with Windows: {n}",
        "dvr_ok": "Xbox Game Bar does not record games in the background",
        "dvr_on": "Xbox Game Bar records games in the background all the time",
        "uptime": "Running without a restart since {date}",
        "space_ok": "Enough free space on every drive",
        "space_low": "{drive} has {free} free of {total}",
        "health_ok": "Every drive reports that it is healthy",
        "health_bad": "{name} reports “{health}”",
        "system_ssd": "Windows is on an SSD: {name}",
        "system_hdd": "Windows is on a hard disk: {name}",
        "disk_errors_ok": "No drive errors in the last {days} days",
        "disk_errors": "Drive errors in the last {days} days: {n}",
        "temp_size": "Temporary files take {size}",
        "temp_size_partial": "Temporary files take at least {size}",
        "crashes_ok": "None in the last {days} days",
        "bsod": "Blue screens in the last {days} days: {n}",
        "resets": "Sudden shutdowns in the last {days} days: {n}",
        "app_crashes_ok": "No program crashed in the last {days} days",
        "app_crashes": "Crashes and hangs in the last {days} days: {n}, most of all {name}",
        "tdr_ok": "The graphics driver did not crash in the last {days} days",
        "tdr": "Graphics driver crashes and errors in the last {days} days: {n}",
        "whea_ok": "No hardware errors in the last {days} days",
        "whea_fatal": "Fatal hardware errors in the last {days} days: {n}",
        "whea_corrected": "Hardware errors corrected in the last {days} days: {n}",
        "devices_ok": "Every device works",
        "devices": "Devices with problems: {n}",
        "devices_conflict": "Devices with problems: {n}, a resource conflict among them",
        "battery": "The battery holds {percent}% of its original charge",
        "av_ok": "{name} is on",
        "av_none": "No antivirus is on",
        "av_many": "Several antiviruses are on at once: {names}",
        "av_old": "{name} has out-of-date virus definitions",
        "wu_ok": "Updates last installed on {date}",
        "wu_old": "Updates last installed on {date}",
        "wu_disabled": "The Windows Update service is disabled",
        "wu_policy": "Automatic updates are turned off by a policy",
        "restart_ok": "No restart is pending",
        "restart_pending": "Windows needs a restart to finish installing updates",
        "support_ok": "{windows} gets security updates until {date}",
        "support_ending": "{windows} gets security updates only until {date}",
        "support_ended": "{windows} stopped getting security updates on {date}",
        "support_win10": "Windows 10 has been out of support since {date}: only Extended Security Updates keep it "
                         "patched",
        "proxy_ok": "No proxy server is set",
        "proxy_on": "Internet traffic goes through a proxy: {server}",
        "hosts_ok": "Nothing Windows needs is blocked",
        "hosts_blocks": "Addresses Windows needs are blocked: {n}",
        "hosts_many": "Entries: {n}, which is very many",
        "item_program_size": "{name} — {size}",
        "item_program_percent": "{name} — {percent}%",
        "item_display": "Display {number}: {width}×{height}, {hz} Hz, up to {max_hz} Hz",
        "item_name": "{name}",
        "item_more": "and {n} more",
        "item_fast_startup": "Fast startup is on: Shut down does not restart Windows, only Restart does",
        "item_drive": "{drive} {free} free of {total} ({percent}%)",
        "item_disk": "{name} ({media}, {bus}): {health}",
        "health_healthy": "healthy",
        "health_warning": "warning",
        "health_unhealthy": "failing",
        "item_event_kind": "{kind}: {n}, last on {date}",
        "kind_bad_block": "Bad blocks",
        "kind_controller": "Controller errors",
        "kind_paging": "Paging errors",
        "kind_retry": "Repeated reads and writes",
        "kind_reset": "Drive resets",
        "kind_ntfs": "File system damage",
        "kind_write": "Lost writes",
        "item_bsod": "{date}: stop code {code}",
        "item_reset": "{date}: turned off without shutting down",
        "item_app_crash": "{name}: crashes {crashes}, hangs {hangs}",
        "item_device": "{name}: {problem}",
        "code_1": "not configured correctly (code 1)",
        "code_3": "the driver is damaged or memory is short (code 3)",
        "code_10": "cannot start (code 10)",
        "code_12": "conflicts with another device over resources (code 12)",
        "code_14": "needs a restart (code 14)",
        "code_18": "its drivers need reinstalling (code 18)",
        "code_19": "its registry settings are damaged (code 19)",
        "code_21": "is being removed (code 21)",
        "code_24": "missing or not working (code 24)",
        "code_28": "no driver installed (code 28)",
        "code_31": "the driver could not be loaded (code 31)",
        "code_32": "the driver is disabled (code 32)",
        "code_37": "the driver failed to start (code 37)",
        "code_39": "the driver is damaged or missing (code 39)",
        "code_41": "the driver loaded but did not find the device (code 41)",
        "code_43": "stopped after it reported problems (code 43)",
        "code_48": "the driver is blocked as incompatible (code 48)",
        "code_52": "the driver is not digitally signed (code 52)",
        "code_other": "error code {code}",
        "item_av": "{name}: {state}",
        "av_on": "on",
        "av_off": "off",
        "av_outdated": "on, definitions out of date",
        "driver_ok": "{name}, driver from {date}",
        "driver_ok_nodate": "{name}",
        "driver_old": "The {name} driver is from {date}",
        "basic_driver": "{name}: the graphics card has no driver",
        "item_adapter": "{name}: driver {version} from {date}",
        "item_adapter_nodate": "{name}: driver {version}",
        "output_ok": "Displays are connected to {name}",
        "output_igpu": "Display {number} is connected to {adapter}, not to {card}",
        "power_capped": "The power plan limits the processor to {percent}% of its speed",
        "ram_reserved": "Windows can use only {total} of the {installed} installed",
        "boot_ok": "No limits and no debugging options",
        "boot_changed": "Changed options: {n}",
        "item_numproc": "Windows uses {n} of {total} logical processors (boot options)",
        "item_maxmem": "Memory is limited by a boot option: {option}",
        "item_testsigning": "Test mode is on: unsigned drivers can load, and anti-cheats such as Riot Vanguard and "
                            "BattlEye refuse to run",
        "item_integrity": "Driver signature checks are turned off",
        "item_verifier": "Driver Verifier is on",
        "item_tdr_off": "Graphics driver recovery (TDR) is turned off",
        "ssd_trim_off": "TRIM is off for the SSD {name}",
        "low_memory": "Windows ran low on memory {n} times in {days} days",
        "services_ok": "No service keeps failing",
        "services_failing": "Services that keep failing: {n}",
        "item_service": "{name}: failures {n}",
        "memtest_ok": "The memory test of {date} found no errors",
        "memtest_errors": "The memory test of {date} found errors",
        "hvci_on": "Memory integrity is on",
        "item_no_mbec": "This processor lacks MBEC/GMET, so memory integrity costs it more",
        "wu_failed": "Updates that failed to install: {n}",
        "item_update_failed": "{name}: error {code}",
        "network_ok": "No IP address conflicts in the last {days} days",
        "ip_conflict": "Another device on the network uses {address} (last on {date})",
        "item_reset_button": "{date}: turned off by holding the power button",
        "kind_tdr": "Driver restarts (TDR)",
        "kind_nvidia": "NVIDIA driver errors",
        "kind_gpu_hang": "Graphics engine hangs",
        "ssd_worn": "{name} has used {wear}% of its rated life",
        "read_errors": "{name} failed to read data {n} times",
        "item_disk_wear": "{name} ({media}, {bus}): {health}, wear {wear}%",
        "item_debug": "Kernel debugging is on",
        "unknown_admin": "Needs administrator rights.",
        "boost_off": "Turbo boost is turned off in the power plan “{name}”",
        "freq_capped": "The power plan holds the processor at {mhz} MHz",
        "card_disabled": "{name} is disabled in Device Manager",
        "nvidia_slow": "NVIDIA driver {version} loses FPS with this Windows update",
        "link_ok": "{name} uses {width} of {max} PCIe lanes",
        "link_narrow": "{name} uses only {width} of {max} PCIe lanes",
        "gpu_power_saving": "Programs set to the power-saving graphics: {n}",
        "rgb_many": "Several lighting programs run at once: {names}",
        "throttled": "The firmware slowed the processor down for {hours} h in {days} days",
        "microcode_old": "Microcode {revision} is older than the {fixed} fix for degradation",
        "microcode_newer": "Microcode {revision} has the fix; {latest} is newer still",
        "microcode_ok": "Microcode {revision} has the latest fixes",
        "x3d_ok": "AMD's 3D V-Cache driver and the Game Bar are in place",
        "x3d_missing": "Games may run on the cores without the extra cache",
        "item_x3d_driver": "AMD's 3D V-Cache Performance Optimizer is not running",
        "item_game_bar_missing": "The Xbox Game Bar is not installed",
        "item_game_mode_off": "Game Mode is off",
        "single_module": "One memory module: the processor uses one memory channel instead of two",
        "xmp_off": "Memory runs at {speed} MT/s but is rated for {rated} MT/s",
        "mixed_modules": "Memory modules of different kinds are mixed",
        "modules_ok": "Modules: {n}, {total} at {speed} MT/s",
        "modules_ok_nospeed": "Modules: {n}, {total}",
        "item_module": "{slot}: {size} {part}, {speed} MT/s",
        "item_module_nospeed": "{slot}: {size} {part}",
        "pool_ok": "Windows' drivers hold {size}",
        "pool_leak": "Windows' drivers hold {size}: a driver may be leaking memory",
        "item_pool_tag": "When memory last ran low, the largest user was the pool tag “{tag}”",
        "pagefile_small": "The page file is limited to {size}",
        "pagefile_drive": "The page file is set on drive {drive}, which is not there",
        "pagefile_no_room": "The page file cannot grow: drive {drive} is almost full",
        "pagefile_missing": "Windows could not create the page file",
        "item_numproc_option": "The boot option {option} limits the processors",
        "item_hpet": "The HPET timer is forced as the system clock (useplatformclock)",
        "item_removable": "All of them come from removable drives, which is usually harmless",
        "item_reset_sleep": "{date}: turned off while going to sleep",
        "item_reset_shutdown": "{date}: turned off while shutting down or hibernating",
        "item_app_crash_module": "{name}: crashes {crashes}, hangs {hangs}, mostly in {module}",
        "item_hint_overlay": "{module} belongs to the {product} overlay: turn it off for this program",
        "item_hint_gpu": "{module} is part of the graphics driver: reinstall the driver cleanly",
        "item_hint_disk": "Error {code}: Windows could not read the program from the drive",
        "item_hint_unstable": "Many different programs crash inside Windows' own code: memory or processor settings "
                              "may be unstable (overclocking, XMP/EXPO, undervolting)",
        "item_wer_off": "Windows Error Reporting is off, so hangs of the graphics card are not recorded",
        "gpu_exceptions": "Graphics driver exceptions in the last {days} days: {n}",
        "kind_nvidia_exception": "NVIDIA graphics exceptions",
        "kind_whea_fatal": "Fatal errors",
        "kind_whea_unstable": "Corrected processor and memory errors",
        "kind_whea_pcie": "Corrected PCI Express errors",
        "kind_whea_other": "Other corrected errors",
        "whea_unstable": "Corrected processor or memory errors in the last {days} days: {n}",
        "core_ok": "No important service is disabled",
        "core_off": "Disabled services: {n}",
        "item_service_off": "{name}: {effect}",
        "effect_updates": "Windows updates stop",
        "effect_install": "programs and Store apps cannot be installed",
        "effect_sound": "no sound",
        "effect_firewall": "the firewall does not work",
        "effect_logs": "logs and system information stop working",
        "effect_tasks": "scheduled tasks do not run",
        "effect_network": "the network connection breaks",
        "effect_clock": "the clock is not synchronised",
        "effect_xbox": "Xbox, Game Pass and Xbox controllers do not work",
        "effect_search": "search in Start and File Explorer is slow",
        "effect_reports": "crashes are not recorded",
        "effect_compression": "memory compression is off",
        "image_ok": "No damage recorded in the Windows system files",
        "image_repairable": "Windows recorded damage in its system files that can be repaired",
        "image_broken": "Windows recorded damage in its system files that cannot be repaired",
        "runtime_ok": "Up to date",
        "runtime_old": "Older than {min}: new programs may crash at start",
        "runtime_missing": "Not installed for every kind of program",
        "item_runtime": "{kind}: {version}",
        "item_runtime_missing": "{kind}: not installed",
        "media_ok": "The media features are installed",
        "media_missing": "This N edition lacks the Media Feature Pack",
        "security_ok": "UAC and the processor vulnerability protection are on",
        "security_off": "Protections turned off: {n}",
        "item_uac_off": "User Account Control (UAC) is turned off completely",
        "item_mitigations_off": "Protection against Spectre and Meltdown is turned off",
        "secure_ok": "UEFI, Secure Boot and TPM 2.0 are on",
        "secure_off": "Turned off or missing: {n}",
        "item_legacy_boot": "Windows starts in legacy BIOS mode, not UEFI",
        "item_secure_boot_off": "Secure Boot is off",
        "item_tpm_missing": "No TPM 2.0",
        "ethernet_slow": "{name} is connected at {speed} Mb/s",
        "system_slow_bus": "Windows is on a {bus} drive: {name}",
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

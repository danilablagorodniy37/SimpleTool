"""Troubleshooting: every verdict on made-up facts, the texts of every finding, and a read-only run on this PC."""
import ctypes
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid
import winreg
from ctypes import wintypes
from unittest import mock

import diagnostics
import engine
import i18n
import sysinfo
from diagnostics import GB, Size, Text

MB = 1024 * 1024
NOW = datetime.datetime(2026, 10, 24, 12, 0)
BALANCED = "381b4222-f694-41f0-9685-ff5bb260df2e"
CARD = "NVIDIA GeForce RTX 4070"
CHIP = "Intel(R) UHD Graphics 770"


def healthy():
    """Facts of a desktop where every check is fine."""
    return {
        "now": NOW,
        "admin": True,
        "memory": {"total": 16 * GB, "avail": 10 * GB, "load": 38, "commit_total": 24 * GB, "commit_avail": 14 * GB},
        "pagefile": {"files": ["?:\\pagefile.sys"], "existing": ["\\??\\C:\\pagefile.sys"]},
        "pool": {"nonpaged": 600 * MB, "paged": 900 * MB},
        "top_memory": [("chrome.exe", 2 * GB), ("discord.exe", 600 * MB)],
        "processes": {"chrome", "discord", "explorer"},
        "cpu": {"load": 12.0, "top": [("chrome.exe", 4.0)], "interrupts": 0.4, "interrupts_now": 1.2},
        "processor": {"name": "AMD Ryzen 7 7800X3D 8-Core Processor", "model": 97, "microcode": 0xA601206},
        "model": "Micro-Star International Co., Ltd. MS-7D76",
        "power": {"scheme": BALANCED, "name": "Balanced", "overlay": "00000000-0000-0000-0000-000000000000",
                  "plugged": True, "battery": False, "saver": False, "max_cpu": 100, "max_cpu1": None, "boost": 2,
                  "max_mhz": 0, "max_mhz1": None},
        "displays": [{"number": 1, "width": 2560, "height": 1440, "hz": 144, "max_hz": 144, "adapter": CARD,
                      "vendor": "10DE", "primary": True}],
        "video": [{"name": CARD, "inf": "oem40.inf", "version": "32.0.16.1088",
                   "pnp": "PCI\\VEN_10DE&DEV_2786&SUBSYS_00000000\\4&1", "code": 0, "date": "2026-07-22T00:00:00"},
                  {"name": CHIP, "inf": "oem8.inf", "version": "32.0.101.7088",
                   "pnp": "PCI\\VEN_8086&DEV_4680&SUBSYS_00000000\\3&1", "code": 0, "date": "2026-06-17T00:00:00"}],
        "vram": {CARD: 12 * GB, CHIP: 2 * GB - 4096},
        "links": {CARD: (16, 16), CHIP: None},
        "gpu_preferences": [],
        "startup": ["Discord", "Steam"],
        "game_dvr": {"background": False},
        "boot": {"options": ["NOEXECUTE=OPTIN", "HYPERVISORLAUNCHTYPE=AUTO"], "verifier": False, "tdr_off": False,
                 "processors": 16, "integrity": diagnostics.CI_ENABLED, "timer": 10_000_000},
        "vbs": {"available": [1, 2, 3, 4, 5, 6, 7, 8], "running": []},
        "cpu_threads": 16,
        "cpu_hardware_threads": 16,
        "modules": [{"size": 8 * GB, "speed": 3200, "configured": 3200, "part": "CMK16GX4M2B3200C16", "maker": "Corsair",
                     "form": 8, "slot": "DIMM A2"},
                    {"size": 8 * GB, "speed": 3200, "configured": 3200, "part": "CMK16GX4M2B3200C16", "maker": "Corsair",
                     "form": 8, "slot": "DIMM B2"}],
        "uptime": 2 * 86400,
        "fast_startup": False,
        "graphics": [f"{CARD} (driver 32.0.16.1088)"],
        "drives": [{"drive": "C:", "total": 500 * GB, "free": 200 * GB, "system": True}],
        "system_disk": 0,
        "trim_off": False,
        "temp": {"size": 1 * GB, "partial": False},
        "cbs": {"largest": {"name": "CBS.log", "size": 7 * MB}, "cabs": 0},
        "crash_files": [],
        "local_dumps": {"enabled": False, "folder": "D:\\Data\\AppData\\Local\\CrashDumps", "dumps": []},
        "live_kernel": {"readable": True, "dumps": [], "components": []},
        "kernel_dumps": {"readable": True, "minidumps": [], "memory_dmp": None, "enabled": 7, "last_crash": None,
                         "count": 5},
        "software": {"programs": {}, "packages": [], "services": {}, "rtss": None},
        "disks": [{"id": "0", "name": "Samsung SSD 980", "media": "SSD", "health": "Healthy", "bus": "NVMe"}],
        "wear": [],
        "devices": [],
        "antivirus": [{"name": "Windows Defender", "state": 0x61100}],
        "adapters": [{"name": "Intel(R) Ethernet Controller I225-V", "speed": 1_000_000_000}],
        "last_update": NOW - datetime.timedelta(days=1),
        "windows_updated": NOW - datetime.timedelta(days=10),
        "image": "Healthy",
        "events": [], "disk_events": [], "nvidia_events": [], "throttle_events": [], "shutdowns": [],
        "service_events": [], "update_events": [], "memory_tests": [], "live_events": [], "whea": [], "app_events": [],
        "disabled_services": [],
        "wer_off": False,
        "vc_runtime": {"x64": (14, 50, 35719, 0), "x86": (14, 50, 35719, 0)},
        "restart_pending": False,
        "update_settings": {"disabled": False, "policy_off": False, "server": None, "blocked": [],
                            "paused_until": None},
        "windows": {"product": "Windows 11", "version": "25H2", "build": 26200, "edition": "Professional",
                    "update": 7000, "server": False, "media": True},
        "firmware": {"uefi": True, "secure_boot": True, "tpm": 2, "anti_cheat": False, "ca2023": "Updated",
                     "ca2023_error": None},
        "security": {"uac_off": False, "mitigations_off": False, "smartscreen_off": False, "zone_off": False,
                     "defender_policies": [], "notifications_off": False, "hidden_pages": [], "blocklist_off": False},
        "recovery": {"enabled": True},
        "time_events": [event("Microsoft-Windows-Time-Service", 37, days_ago=2, level=4)],
        "defender_exclusions": {"paths": [], "extensions": [], "processes": []},
        "threats": [],
        "firewall": {"domain": True, "private": True, "public": True},
        "firewall_products": [],
        "smb1": [],
        "remote_desktop": {"on": False, "nla_off": False, "wrapper": False},
        "browser_policies": [],
        "added_roots": [],
        "local_users": [{"name": "Administrator", "enabled": False, "sid": "S-1-5-21-1-2-3-500"},  # made-up test data, secret-scan: allow
                        {"name": "Guest", "enabled": False, "sid": "S-1-5-21-1-2-3-501"},  # made-up test data, secret-scan: allow
                        {"name": "Player", "enabled": True, "sid": "S-1-5-21-1-2-3-1001"}],  # made-up test data, secret-scan: allow
        "account_settings": {"hidden": [], "autologon_password": False},
        "bitlocker": {"conversion": 0, "protection": 0, "recovery": []},
        "defender": {"mode": "Normal", "realtime": True, "tamper": True},
        "managed": {"domain": False, "entra": False, "mdm": False},
        "blocked": {"programs": [], "locks": [], "disallowed": [], "firewall": []},
        "disallowed": [],
        "proxy": {"enabled": False, "server": "", "pac": ""},
        "hosts": {"entries": 0, "blocked": []},
        "sleep": {"available": True, "causes": []},
        "network_setup": {"ipv6": 0, "split": 3670016, "teredo_policy_off": False, "ip_helper_off": False,
                          "gaming": False},
        "teredo": 0,
        "startup_impact": [{"name": "Discord", "cpu": 420, "disk": 900_000, "starts": 5}],
        "perf_events": [boot(days_ago=d) for d in (1, 3, 6)],
        "drive_health": {"0": nvme()},
        "drive_links": {"0": (4, 4, 4, 4)},
        "volumes": [{"drive": "C", "health": 0}],
        "dirty": [],
        "app_platform": {"packages": [p + "_1.0.0.0_x64__8wekyb3d8bbwe" for p in (
            "microsoft.windowsstore", "microsoft.sechealthui", "microsoft.desktopappinstaller")] +
            ["microsoftwindows.client.cbs_1000.26100.0.0_x64__cw5n1h2txyewy"],
            "webview2": "141.0.3537.71", "deprovisioned": [], "gaming": False},
        "wmi": 0,
        "wmi_repository": 0,
        "watch": watch_facts(),
        "stress": stress_facts(),
        "disk_speed": {"sequential": 3200.0, "random_ms": 0.1, "random_p95": 0.2, "read_mb": 2048, "source": "disk"},
        "connection": connection_facts(),
        "shares": [],
    }


def boot(days_ago=1, total=30_000, after_install=False):
    """Event 100 of Diagnostics-Performance: one start of Windows."""
    return {"id": 100, "time": NOW - datetime.timedelta(days=days_ago),
            "data": {"BootTime": str(total), "MainPathBootTime": str(total // 2), "BootPostBootTime": str(total // 2),
                     "BootIsRebootAfterInstall": "true" if after_install else "false"}}


def culprit(event_id, name, delay, days_ago=1):
    """An event of Diagnostics-Performance that names what slowed a start or a shutdown."""
    return {"id": event_id, "time": NOW - datetime.timedelta(days=days_ago),
            "data": {"Name": name, "FriendlyName": "", "TotalTime": str(delay + 1000), "DegradationTime": str(delay)}}


def nvme(**changes):
    """The health log of an NVMe drive in good shape."""
    report = {"kind": "nvme", "critical": 0, "temperature": 41, "spare": 100, "spare_threshold": 10, "used": 3,
              "written": 30 * 10 ** 12, "hours": 2500, "unsafe": 12, "media_errors": 0, "hot_minutes": 0}
    report.update(changes)
    return report


# Checks that have nothing to say about the healthy desktop above
SILENT = {"battery", "memory_test", "memory_integrity", "cpu_microcode", "x3d_cores", "gpu_preference",
          "rgb_software", "throttling", "media_pack", "video_memory", "remote_tools", "dead_shares"}


def event(provider, event_id, days_ago=1, level=2, args=(), minutes=0):
    moment = NOW - datetime.timedelta(days=days_ago, minutes=minutes)
    return {"id": event_id, "provider": provider, "level": level, "time": moment, "args": list(args)}


def verdict(check, **changes):
    facts = healthy()
    facts.update(changes)
    return diagnostics.VERDICTS[check](facts)


def render(lang, key, params):
    """A line as the window shows it, with nested texts filled in."""
    values = {}
    for name, value in params.items():
        if isinstance(value, Text):
            value = render(lang, value, {n: v for n, v in params.items() if not isinstance(v, Text)})
        elif isinstance(value, Size):
            value = f"{value / GB:.1f} GB"
        values[name] = value
    return i18n.TEXTS[lang]["diag_lines"][key].format(**values)


def render_all(findings):
    """Every line of every finding in every language: a missing text or value fails here, not in the window."""
    for lang in i18n.TEXTS:
        for finding in findings:
            render(lang, finding.line, finding.params)
            for key, params in finding.items:
                render(lang, key, params)
            for action in finding.actions:
                assert "act_" + action in i18n.TEXTS[lang]["ui"], (lang, action)


class Verdicts(unittest.TestCase):
    def severity(self, check, **changes):
        return verdict(check, **changes).severity

    def assertRenders(self, finding):
        self.assertIsNotNone(finding)
        render_all([finding])

    def test_a_healthy_pc_is_all_good(self):
        findings = diagnostics.evaluate(healthy())
        self.assertEqual({f.check: f.severity for f in findings if f.severity != "ok"}, {})
        self.assertEqual({f.check for f in findings}, {c for c, _ in diagnostics.CHECKS} - SILENT)
        render_all(findings)

    def test_nothing_known_means_not_checked(self):
        findings = diagnostics.evaluate({"now": NOW})
        self.assertTrue(findings)
        self.assertEqual({f.severity for f in findings}, {"unknown"})
        render_all(findings)

    def test_memory(self):
        memory = healthy()["memory"]
        self.assertEqual(self.severity("ram_load", memory=dict(memory, load=92)), "problem")
        finding = verdict("ram_load", memory=dict(memory, load=85))
        self.assertEqual(finding.severity, "warning")
        self.assertEqual([p["name"] for _, p in finding.items], ["chrome.exe", "discord.exe"])
        self.assertIn("memory", finding.actions, "the memory limiter is offered")
        one = [dict(healthy()["modules"][0], size=4 * GB)]
        self.assertEqual(self.severity("ram_size", memory=dict(memory, total=int(3.4 * GB)), modules=one), "problem")
        self.assertEqual(self.severity("ram_size", memory=dict(memory, total=6 * GB), modules=[]), "warning")
        self.assertEqual(self.severity("ram_size", memory=dict(memory, total=int(15.8 * GB))), "ok",
                         "16 GB installed shows as a little less")
        finding = verdict("ram_size", memory=dict(memory, total=int(7.9 * GB)))
        self.assertEqual((finding.severity, finding.line), ("warning", "ram_reserved"), "half of 16 GB is missing")
        self.assertEqual(self.severity("ram_size", memory=dict(memory, total=int(7.9 * GB)), modules=[]), "ok",
                         "8 GB is enough when the modules are not known")
        apu = "AMD Radeon(TM) 780M Graphics"
        laptop = {"video": [{"name": apu, "pnp": "PCI\\VEN_1002&DEV_15BF\\4&1", "code": 0}], "vram": {apu: 8 * GB}}
        self.assertEqual(self.severity("ram_size", memory=dict(memory, total=int(7.8 * GB)), **laptop), "ok",
                         "8 GB set aside for the processor's graphics is not missing")

    def test_memory_modules(self):
        module = healthy()["modules"][0]
        single = verdict("memory_config", modules=[dict(module, size=16 * GB)])
        self.assertEqual((single.severity, single.line), ("warning", "single_module"))
        laptop = dict(healthy()["power"], battery=True)
        self.assertEqual(self.severity("memory_config", modules=[dict(module, form=12)], power=laptop), "ok",
                         "laptops often have one module or soldered memory")
        slow = [dict(module, part="F4-3600C16D-16GTZNC", configured=2133, slot=slot) for slot in ("A2", "B2")]
        finding = verdict("memory_config", modules=slow)
        self.assertEqual((finding.severity, finding.line, finding.params["rated"]), ("info", "xmp_off", 3600))
        mixed = [module, dict(module, part="KF432C16BB/8", slot="DIMM B2")]
        self.assertEqual(verdict("memory_config", modules=mixed).line, "mixed_modules")
        self.assertIsNone(verdict("memory_config", model="Microsoft Corporation Virtual Machine"))
        self.assertEqual(verdict("memory_config", modules=[dict(m, configured=0) for m in healthy()["modules"]]).line,
                         "modules_ok_nospeed")
        for part, speed in (("F5-6000J3038F16G", 6000), ("CMK16GX4M2B3200C16", 3200), ("KF436C17BB/8", 3600),
                            ("KF426C16BB/8", 2666), ("BL8G36C16U4B.M8FE1", 3600), ("TF3D416G3600HC18J", 3600),
                            ("M378A1K43EB2-CWE", None)):
            self.assertEqual(diagnostics.rated_speed(part), speed, part)

    def test_driver_memory(self):
        self.assertEqual(self.severity("kernel_memory", pool={"nonpaged": 5 * GB, "paged": GB}), "problem")
        finding = verdict("kernel_memory", pool={"nonpaged": int(2.5 * GB), "paged": GB},
                          events=[event("Microsoft-Windows-Resource-Exhaustion-Detector", 2004, level=3,
                                        args=["game.exe", "", "", "Ndis"])])
        self.assertEqual((finding.severity, finding.items), ("warning", [("item_pool_tag", {"tag": "Ndis"})]))
        self.assertEqual(self.severity("kernel_memory", pool={"nonpaged": int(1.2 * GB), "paged": GB},
                                       memory=dict(healthy()["memory"], total=8 * GB)), "warning",
                         "a tenth of the RAM")
        self.assertEqual(self.severity("kernel_memory", pool={"nonpaged": int(1.2 * GB), "paged": GB}), "ok")

    def test_page_file(self):
        memory, page = healthy()["memory"], healthy()["pagefile"]
        self.assertEqual(self.severity("pagefile", pagefile=dict(page, files=[])), "warning")
        self.assertEqual(self.severity("pagefile", memory=dict(memory, commit_avail=1 * GB)), "problem")
        exhaustion = "Microsoft-Windows-Resource-Exhaustion-Detector"
        low = [event(exhaustion, 2004, level=3, args=["chrome.exe", "game.exe", ""]),
               event(exhaustion, 2004, 3, level=3, args=["game.exe", "chrome.exe", "obs64.exe"]),
               event(exhaustion, 2004, 5, level=3, args=["game.exe", "", ""])]
        finding = verdict("pagefile", events=low)
        self.assertEqual((finding.severity, finding.line, finding.params["n"]), ("warning", "low_memory", 3))
        self.assertEqual([p["name"] for _, p in finding.items], ["game.exe", "chrome.exe", "obs64.exe"],
                         "the programs that took most, most often first")
        small = dict(page, files=["C:\\pagefile.sys 512 1024"])
        self.assertEqual(verdict("pagefile", pagefile=small).line, "pagefile_small")
        self.assertEqual(self.severity("pagefile", pagefile=dict(page, files=["C:\\pagefile.sys 16384 16384"])), "ok")
        gone = dict(page, files=["E:\\pagefile.sys 0 0"])
        self.assertEqual(verdict("pagefile", pagefile=gone).line, "pagefile_drive")
        full = [{"drive": "C:", "total": 500 * GB, "free": 3 * GB, "system": True}]
        self.assertEqual(verdict("pagefile", drives=full).line, "pagefile_no_room", "system managed, no room")
        self.assertEqual(verdict("pagefile", pagefile=dict(page, existing=[])).line, "pagefile_missing")

    def test_processor_and_power(self):
        self.assertEqual(self.severity("cpu_load", cpu={"load": 85.0, "top": [("miner.exe", 70.0)]}), "warning")
        power = healthy()["power"]
        saver = dict(power, scheme=diagnostics.POWER_SAVER, name="Power saver")
        self.assertEqual(self.severity("power_plan", power=saver), "warning")
        self.assertEqual(self.severity("power_plan", power=dict(saver, plugged=False, battery=True)), "ok",
                         "a laptop on battery may save power")
        self.assertEqual(self.severity("power_plan", power=dict(power, overlay=diagnostics.OVERLAY_EFFICIENCY)),
                         "warning")
        self.assertEqual(self.severity("power_plan", power=dict(power, saver=True, plugged=False, battery=True)),
                         "info")
        capped = verdict("power_plan", power=dict(power, max_cpu=99))
        self.assertEqual((capped.severity, capped.params["percent"]), ("warning", 99), "turbo boost is off")
        self.assertEqual(verdict("power_plan", power=dict(power, max_cpu1=80)).params["percent"], 80,
                         "the efficient cores of a hybrid processor")
        self.assertEqual(self.severity("power_plan", power=dict(power, max_cpu=50, plugged=False, battery=True)),
                         "ok", "a laptop on battery may hold the processor back")
        self.assertEqual(verdict("power_plan", power=dict(power, boost=0)).line, "boost_off")
        mhz = verdict("power_plan", power=dict(power, max_mhz=2400))
        self.assertEqual((mhz.line, mhz.params["mhz"]), ("freq_capped", 2400))

    def test_intel_microcode(self):
        raptor = {"name": "13th Gen Intel(R) Core(TM) i9-13900K", "model": 183, "microcode": 0x125}
        old = verdict("cpu_microcode", processor=raptor)
        self.assertEqual((old.severity, old.params["revision"]), ("warning", "0x125"))
        self.assertRenders(old)
        crashing = verdict("cpu_microcode", processor=raptor, whea=[event("Microsoft-Windows-WHEA-Logger", 19, level=3)])
        self.assertEqual(crashing.severity, "problem", "it already crashes: the processor may have degraded")
        self.assertEqual(self.severity("cpu_microcode", processor=dict(raptor, microcode=0x12B)), "info")
        self.assertEqual(self.severity("cpu_microcode", processor=dict(raptor, microcode=0x12F)), "ok")
        self.assertIsNone(verdict("cpu_microcode", processor=dict(raptor, model=191)),
                          "the i5-13400 on the Alder Lake die is not affected")
        self.assertIsNone(verdict("cpu_microcode", processor=dict(raptor, name="13th Gen Intel(R) Core(TM) i7-13700H")),
                          "a laptop processor")
        self.assertIsNone(verdict("cpu_microcode", processor=dict(raptor, name="12th Gen Intel(R) Core(TM) i7-12700K",
                                                                    model=151)))
        self.assertEqual(self.severity("cpu_microcode", processor=dict(raptor, microcode=None)), "unknown")

    def test_ryzen_x3d(self):
        x3d = {"name": "AMD Ryzen 9 7950X3D 16-Core Processor", "model": 97, "microcode": 1}
        self.assertIsNone(verdict("x3d_cores"), "one core die: nothing to steer")
        finding = verdict("x3d_cores", processor=x3d, x3d={"driver": False},
                          game_bar={"installed": False, "game_mode": True})
        self.assertEqual((finding.severity, [k for k, _ in finding.items]),
                         ("warning", ["item_x3d_driver", "item_game_bar_missing"]))
        self.assertEqual(self.severity("x3d_cores", processor=x3d, x3d={"driver": True},
                                       game_bar={"installed": True, "game_mode": True}), "ok")
        self.assertEqual(verdict("x3d_cores", processor=x3d, x3d={"driver": True},
                                 game_bar={"installed": True, "game_mode": False}).items,
                         [("item_game_mode_off", {})])

    def test_graphics(self):
        card, chip = healthy()["video"]
        basic = dict(card, name="Microsoft Basic Display Adapter", inf="display.inf", date="2006-06-21T00:00:00")
        finding = verdict("graphics_driver", video=[basic, chip])
        self.assertEqual((finding.severity, finding.params["name"]), ("problem", "Microsoft Basic Display Adapter"))
        vmware = dict(basic, pnp="PCI\\VEN_15AD&DEV_0405\\3&1")
        self.assertNotEqual(self.severity("graphics_driver", video=[vmware]), "problem", "a virtual machine")
        self.assertEqual(self.severity("graphics_driver", video=[dict(card, date="2024-11-01T00:00:00"), chip]),
                         "info", "a card driver two years old")
        self.assertEqual(self.severity("graphics_driver", video=[chip]), "ok",
                         "the processor's graphics get their driver from the PC maker, so its age says little")
        remote = {"name": "Microsoft Remote Display Adapter", "inf": "rdpidd.inf", "pnp": "SWD\\RemoteDisplay"}
        self.assertIsNone(verdict("graphics_driver", video=[remote]), "a remote session has no graphics card")
        verdict("graphics_driver", video=[dict(card, date="")])  # no driver date: still a verdict
        disabled = {"name": CARD, "code": 22, "cls": "Display", "pnp": card["pnp"]}
        finding = verdict("graphics_driver", video=[chip], devices=[disabled])
        self.assertEqual((finding.severity, finding.line), ("warning", "card_disabled"))
        old_nvidia = dict(card, version="32.0.15.7680")  # 576.80
        self.assertEqual(diagnostics.nvidia_version(old_nvidia["version"]), 576.80)
        self.assertEqual(diagnostics.nvidia_version("32.0.15.8194"), 581.94)
        slow = verdict("graphics_driver", video=[old_nvidia, chip], windows=dict(healthy()["windows"], update=7019))
        self.assertEqual((slow.severity, slow.line, slow.params["version"]), ("warning", "nvidia_slow", "576.80"))
        self.assertEqual(verdict("graphics_driver", video=[old_nvidia, chip],
                                 windows=dict(healthy()["windows"], update=6000)).line, "driver_ok",
                         "before the update that slowed it down")

        screen = healthy()["displays"][0]
        on_chip = dict(screen, adapter=chip["name"], vendor="8086")
        finding = verdict("display_output", displays=[on_chip])
        self.assertEqual((finding.severity, finding.params["card"]), ("warning", card["name"]))
        second = dict(on_chip, number=2, primary=False)
        self.assertEqual(self.severity("display_output", displays=[screen, second]), "info",
                         "a second monitor on the processor's graphics is a choice")
        laptop = dict(healthy()["power"], battery=True)
        self.assertIsNone(verdict("display_output", displays=[on_chip], power=laptop),
                          "laptops send the picture through the processor's graphics by design")
        self.assertIsNone(verdict("display_output", video=[chip], displays=[on_chip]), "no graphics card")
        broken = dict(card, code=43)
        self.assertIsNone(verdict("display_output", video=[broken, chip], displays=[on_chip]),
                          "a card that does not work is a device problem")
        for name, vendor, discrete in (("AMD Radeon RX 7800 XT", "1002", True), ("AMD Radeon(TM) Graphics", "1002", False),
                                       ("AMD Radeon RX Vega 11 Graphics", "1002", False),
                                       ("Intel(R) Arc(TM) A770 Graphics", "8086", True),
                                       ("Intel(R) Arc(TM) A370M Graphics", "8086", True),
                                       ("Intel(R) Arc(TM) B580 Graphics", "8086", True),
                                       ("Intel(R) Arc(TM) B390 GPU", "8086", False),
                                       ("Intel(R) Arc(TM) Graphics", "8086", False), (CARD, "10DE", True)):
            self.assertEqual(diagnostics.is_discrete(vendor, name), discrete, name)

    def test_graphics_card_lanes_and_preference(self):
        narrow = verdict("gpu_link", links={CARD: (4, 16)})
        self.assertEqual((narrow.severity, narrow.params["width"]), ("warning", 4))
        self.assertEqual(self.severity("gpu_link", links={CARD: (8, 16)}), "ok", "x8 costs only a few percent")
        self.assertIsNone(verdict("gpu_link", links={CARD: (4, 16)}, power=dict(healthy()["power"], battery=True)))
        self.assertIsNone(verdict("gpu_link", links={}))
        programs = verdict("gpu_preference", gpu_preferences=["C:\\Games\\game.exe"])
        self.assertEqual((programs.severity, programs.items), ("info", [("item_name", {"name": "game.exe"})]))
        self.assertIsNone(verdict("gpu_preference", gpu_preferences=["C:\\Games\\game.exe"],
                                  video=[healthy()["video"][1]]), "nothing to choose between")

    def test_refresh_rate(self):
        slow = [{"number": 1, "width": 2560, "height": 1440, "hz": 60, "max_hz": 144}]
        finding = verdict("refresh_rate", displays=slow)
        self.assertEqual((finding.severity, finding.params["hz"], finding.params["max_hz"]), ("warning", 60, 144))
        on_battery = dict(healthy()["power"], battery=True, plugged=False)
        self.assertEqual(self.severity("refresh_rate", displays=slow, power=on_battery), "info",
                         "laptops lower the rate on battery")
        almost = [{"number": 1, "width": 1920, "height": 1080, "hz": 59, "max_hz": 60}]
        self.assertEqual(self.severity("refresh_rate", displays=almost), "ok")
        self.assertIsNone(verdict("refresh_rate", displays=[]), "no display on the desktop: nothing to say")

    def test_lighting_programs(self):
        self.assertIsNone(verdict("rgb_software", processes={"icue", "chrome"}), "one lighting program")
        finding = verdict("rgb_software", processes={"icue", "corsair.service", "lightingservice", "chrome"})
        self.assertEqual((finding.severity, finding.params["names"]), ("info", "ASUS Aura, Corsair iCUE"))

    def test_boot_options(self):
        boot = healthy()["boot"]
        limited = dict(boot, options=boot["options"] + ["NUMPROC=2", "TRUNCATEMEMORY=0X100000000"], processors=2,
                       integrity=diagnostics.CI_ENABLED | diagnostics.CI_TESTSIGN)
        finding = verdict("boot_options", boot=limited)
        self.assertEqual((finding.severity, finding.params["n"]), ("warning", 3))
        self.assertEqual([key for key, _ in finding.items], ["item_numproc", "item_maxmem", "item_testsigning"])
        self.assertEqual(finding.items[0][1], {"n": 2, "total": 16})
        self.assertEqual(self.severity("boot_options", boot=dict(boot, options=["NUMPROC=16"])), "ok",
                         "all processors")
        unknown_count = verdict("boot_options", boot=dict(boot, options=["NUMPROC=4"]), cpu_threads=None,
                                cpu_hardware_threads=None)
        self.assertEqual(unknown_count.items, [("item_numproc_option", {"option": "NUMPROC=4"})])
        unchecked = verdict("boot_options", boot=dict(boot, integrity=diagnostics.CI_DEBUG))
        self.assertEqual([key for key, _ in unchecked.items], ["item_integrity", "item_debug"])
        self.assertEqual(self.severity("boot_options", boot=dict(boot, integrity=None)), "ok",
                         "the flags cannot be read")
        self.assertEqual(verdict("boot_options", boot=dict(boot, timer=diagnostics.HPET_FREQUENCY)).items,
                         [("item_hpet", {})])
        self.assertEqual(self.severity("boot_options", boot=dict(boot, verifier=True)), "warning")
        self.assertEqual(self.severity("boot_options", boot=dict(boot, tdr_off=True)), "warning")

    def test_throttling(self):
        power = "Microsoft-Windows-Kernel-Processor-Power"
        hours = [event(power, 37, day, level=3, args=["0", "1", "1800"]) for day in (1, 2, 3)]
        finding = verdict("throttling", throttle_events=hours)
        self.assertEqual((finding.severity, finding.params["hours"]), ("info", 1.5))
        self.assertIsNone(verdict("throttling", throttle_events=hours[:1]), "half an hour in a week")
        self.assertIsNone(verdict("throttling", throttle_events=hours, power=dict(healthy()["power"], battery=True)),
                          "laptops slow down by design")

    def test_startup_recording_and_uptime(self):
        self.assertEqual(self.severity("startup_apps", startup=[f"App {i}" for i in range(12)]), "warning")
        self.assertEqual(self.severity("game_dvr", game_dvr={"background": True}), "warning")
        finding = verdict("uptime", uptime=8 * 86400, fast_startup=True)
        self.assertEqual(finding.severity, "warning")
        self.assertEqual(finding.params["date"], datetime.date(2026, 10, 16))
        self.assertEqual(finding.items, [("item_fast_startup", {})])

    def test_free_space(self):
        def drives(free, system=True, total=500 * GB):
            return [{"drive": "C:", "total": total, "free": free, "system": system}]

        self.assertEqual(self.severity("disk_space", drives=drives(4 * GB)), "problem")
        self.assertEqual(self.severity("disk_space", drives=drives(15 * GB)), "warning")
        self.assertEqual(self.severity("disk_space", drives=drives(60 * GB, total=2000 * GB)), "ok",
                         "3% of a big drive is still plenty")
        data = drives(200 * GB) + [{"drive": "D:", "total": 1000 * GB, "free": 1 * GB, "system": False}]
        finding = verdict("disk_space", drives=data)
        self.assertEqual((finding.severity, finding.params["drive"]), ("info", "D:"))

    def test_drive_health_and_type(self):
        disk = healthy()["disks"][0]
        self.assertEqual(self.severity("disk_health", disks=[dict(disk, health="Warning")]), "warning")
        finding = verdict("disk_health", disks=[dict(disk, health="Unhealthy")])
        self.assertEqual(finding.severity, "problem")
        self.assertEqual(finding.params["health"], "health_unhealthy")
        self.assertEqual(self.severity("disk_health", disks=[dict(disk, health="Unknown")]), "ok",
                         "a USB bridge or RAID that says nothing")
        # Windows' counters, where the drive's own report could not be read
        worn = verdict("disk_health", wear=[{"id": "0", "wear": 95, "read_errors": None}], drive_health={})
        self.assertEqual((worn.severity, worn.line), ("warning", "ssd_worn"))
        self.assertEqual(self.severity("disk_health", wear=[{"id": "0", "wear": 100, "read_errors": None}],
                                       drive_health={}), "problem")
        self.assertEqual(verdict("disk_health", wear=[{"id": "0", "wear": 3, "read_errors": 2}],
                                 drive_health={}).line, "read_errors")
        self.assertEqual(verdict("disk_health", wear=[{"id": "0", "wear": 0, "read_errors": None}]).items[0][1]["wear"],
                         3, "the drive's own report wins over Windows' counter")
        self.assertEqual(self.severity("system_drive", disks=[dict(disk, media="HDD")]), "warning")
        self.assertEqual(verdict("system_drive", trim_off=True).line, "ssd_trim_off")
        self.assertEqual(verdict("system_drive", trim_off=True, disks=[dict(disk, media="HDD")]).line, "system_hdd",
                         "a hard disk has no use for TRIM")
        self.assertEqual(verdict("system_drive", disks=[dict(disk, bus="MMC", media="Unspecified")]).line,
                         "system_slow_bus", "eMMC flash")
        self.assertIsNone(verdict("system_drive", disks=[dict(disk, media="Unspecified")]),
                          "a virtual drive says nothing about its type")
        self.assertEqual(self.severity("system_drive", system_disk=None), "unknown")

    def test_drive_errors(self):
        self.assertEqual(self.severity("disk_errors", disk_events=[event("disk", 7, args=["\\Device\\Harddisk0\\DR0"])]),
                         "problem")
        self.assertEqual(self.severity("disk_errors", disk_events=[event("stornvme", 129, level=3)]), "warning")
        self.assertEqual(self.severity("disk_errors", disk_events=[event("Microsoft-Windows-Ntfs", 55)]), "problem")
        self.assertEqual(self.severity("disk_errors", disk_events=[event("disk", 7, days_ago=40)]), "ok", "too old")
        self.assertEqual(self.severity("disk_errors", disk_events=[event("disk", 7, level=4)]), "ok", "information")
        finding = verdict("disk_errors", disk_events=[event("disk", 153, level=3), event("disk", 153, 2, level=3)])
        self.assertEqual(finding.items, [("item_event_kind", {"kind": "kind_retry", "n": 2,
                                                              "date": datetime.date(2026, 10, 23)})])
        stick = healthy()["disks"] + [{"id": "3", "name": "SanDisk Cruzer", "media": "Unspecified", "health": "Healthy",
                                       "bus": "USB"}]
        removed = verdict("disk_errors", disks=stick, disk_events=[event("disk", 51, level=3,
                                                                       args=["\\Device\\Harddisk3\\DR3"])])
        self.assertEqual((removed.severity, removed.items[-1]), ("info", ("item_removable", {})),
                         "a memory stick pulled out")
        gone = verdict("disk_errors", disk_events=[event("disk", 11, args=["\\Device\\Harddisk2\\DR3"])])
        self.assertEqual((gone.severity, gone.items[-1]), ("info", ("item_removable", {})),
                         "a disk that is not on the PC now: a stick or phone unplugged since")
        self.assertEqual(self.severity("disk_errors", disks=[],
                                       disk_events=[event("disk", 11, args=["\\Device\\Harddisk2\\DR3"])]), "problem",
                         "without the list of disks nothing says the disk is gone")
        self.assertEqual(self.severity("disk_errors", disk_events=[event("disk", 11, args=["\\Device\\Harddisk0\\DR0"])]),
                         "problem", "the disk is still there")

    def test_temporary_files(self):
        self.assertEqual(self.severity("temp_files", temp={"size": 6 * GB, "partial": False}), "warning")
        self.assertEqual(verdict("temp_files", temp={"size": 2 * GB, "partial": True}).line, "temp_size_partial")

    def test_crashes(self):
        bsod = event("Microsoft-Windows-WER-SystemErrorReporting", 1001, args=["0x0000009f (0x3, 0x0)", "C:\\x"])
        finding = verdict("crashes", events=[bsod])
        self.assertEqual((finding.severity, finding.items[0][1]["code"]), ("problem", "0x0000009f"))
        stop = event("Microsoft-Windows-Kernel-Power", 41, level=1, args=["209", "0"])
        self.assertEqual(verdict("crashes", events=[stop]).items[0][1]["code"], "0x000000D1")
        reset = event("Microsoft-Windows-Kernel-Power", 41, level=1, args=["0", "0"])
        unexpected = event("EventLog", 6008)
        finding = verdict("crashes", events=[reset, unexpected])
        self.assertEqual((finding.severity, finding.params["n"]), ("warning", 1), "41 and 6008 are the same shutdown")
        self.assertEqual(finding.items[0][0], "item_reset")
        self.assertEqual(verdict("crashes", events=[unexpected]).params["n"], 1)

        def power_lost(sleep, button="0"):
            return event("Microsoft-Windows-Kernel-Power", 41, level=1, args=["0"] * 5 + [sleep, button, "0", "16"])

        self.assertEqual(verdict("crashes", events=[power_lost("0", "133000000000000000")]).items[0][0],
                         "item_reset_button")
        self.assertEqual(verdict("crashes", events=[power_lost("6")]).items[0][0], "item_reset_shutdown",
                         "Windows did not finish shutting down")
        self.assertEqual(verdict("crashes", events=[power_lost("4")]).items[0][0], "item_reset_sleep")

    def test_program_crashes(self):
        def crash(name, module="game.dll", code="c0000005", days_ago=1):
            return event("Application Error", 1000, days_ago,
                         args=[name, "1.0", "0", module, "1.0", "0", code, "0x0", "1"])

        crashes = [crash("game.exe") for _ in range(3)]
        finding = verdict("app_crashes", app_events=crashes + [event("Application Hang", 1002, args=["app.exe"])])
        self.assertEqual((finding.severity, finding.params["name"], finding.params["n"]), ("warning", "game.exe", 4))
        self.assertEqual(finding.items[0], ("item_app_crash_module", {"name": "game.exe", "crashes": 3, "hangs": 0,
                                                                      "module": "game.dll"}))
        self.assertEqual(self.severity("app_crashes", app_events=crashes[:1]), "info")
        self.assertEqual(self.severity("app_crashes", app_events=[crash("game.exe", days_ago=20)]), "ok")
        overlay = verdict("app_crashes", app_events=[crash("game.exe", "RTSSHooks64.dll")])
        self.assertIn(("item_hint_overlay", {"module": "RTSSHooks64.dll", "product": "RivaTuner Statistics Server"}),
                      overlay.items)
        gpu = verdict("app_crashes", app_events=[crash("game.exe", "nvwgf2umx.dll")])
        self.assertIn(("item_hint_gpu", {"module": "nvwgf2umx.dll"}), gpu.items)
        disk = verdict("app_crashes", app_events=[crash("game.exe", code="c0000006")])
        self.assertIn(("item_hint_disk", {"code": "0xC0000006"}), disk.items)
        everywhere = [crash(f"app{i}.exe", "ntdll.dll") for i in range(4)]
        self.assertIn(("item_hint_unstable", {}), verdict("app_crashes", app_events=everywhere).items)
        self.assertNotIn(("item_hint_unstable", {}), verdict("app_crashes", app_events=everywhere[:3]).items)
        self.assertRenders(verdict("app_crashes", app_events=everywhere + crashes))

    def test_temporary_files_breakdown(self):
        temp = {"size": 4 * GB, "files": 41_000, "partial": False,
                "top": [{"name": "claude\\", "size": 1300 * MB, "files": 32_000}, {"name": "big.iso", "size": 400 * MB, "files": 1},
                        {"name": "small\\", "size": 20 * MB, "files": 3}],
                "families": [{"pattern": "tree-sit*.dll", "n": 3000, "size": 2 * GB}, {"pattern": "x*.log", "n": 5, "size": 0}]}
        finding = verdict("temp_files", temp=temp)
        self.assertEqual((finding.severity, finding.line, finding.params["files"]), ("warning", "temp_many", 41_000))
        self.assertEqual([key for key, _ in finding.items], ["item_temp_top", "item_temp_file", "item_temp_family"])
        self.assertEqual(finding.items[2][1]["n"], 3000)
        few = verdict("temp_files", temp=dict(temp, files=200, size=1 * GB))
        self.assertEqual((few.severity, few.line), ("ok", "temp_size"))
        self.assertEqual(verdict("temp_files", temp=dict(temp, partial=True)).line, "temp_many_partial")
        self.assertEqual(verdict("temp_files", temp=dict(temp, partial=True, files=10)).line, "temp_size_partial")
        servicing = verdict("temp_files", cbs={"largest": {"name": "CbsPersist_20261001.log", "size": 2 * GB}, "cabs": 12})
        self.assertEqual(servicing.severity, "warning")
        self.assertEqual([key for key, _ in servicing.items], ["item_cbs_large", "item_cbs_cabs"])
        self.assertEqual(self.severity("temp_files", cbs={"largest": None, "cabs": None}), "ok")
        self.assertRenders(servicing)
        self.assertRenders(finding)

    def test_blue_screen_dumps(self):
        day = datetime.timedelta(days=1)
        dumps = {"readable": True, "minidumps": [NOW - 2 * day, NOW - 5 * day], "memory_dmp": None, "enabled": 7,
                 "last_crash": NOW - 2 * day, "count": 5}
        finding = verdict("crashes", kernel_dumps=dumps)
        self.assertEqual((finding.severity, finding.params["n"]), ("problem", 2), "the dump files witness the crashes")
        self.assertEqual(finding.items[0], ("item_minidump", {"date": (NOW - 2 * day).date()}))
        remembered = verdict("crashes", kernel_dumps=dict(dumps, minidumps=[]))
        self.assertEqual((remembered.severity, remembered.items[0][0]), ("problem", "item_last_crash"))
        old = verdict("crashes", kernel_dumps=dict(dumps, minidumps=[NOW - 100 * day], last_crash=NOW - 100 * day))
        self.assertEqual(old.severity, "ok")
        bsod = event("Microsoft-Windows-WER-SystemErrorReporting", 1001, args=["0x0000009f (0x3, 0x0)", "C:\\x"])
        both = verdict("crashes", events=[bsod], kernel_dumps=dumps)
        self.assertEqual(both.params["n"], 1, "with the event logged, the dump is the same crash")
        self.assertNotIn("item_minidump", [key for key, _ in both.items])
        off = verdict("crashes", kernel_dumps=dict(dumps, minidumps=[], last_crash=None, enabled=0,
                                                   memory_dmp={"time": NOW - 3 * day, "size": 3 * GB}))
        self.assertEqual(off.severity, "ok")
        self.assertEqual([key for key, _ in off.items], ["item_dumps_disabled", "item_memory_dmp"])
        self.assertIn("system_properties", off.actions)
        self.assertRenders(off)
        self.assertRenders(finding)

    def test_local_dumps_and_shader_hint(self):
        def crash(name, module="game.dll"):
            return event("Application Error", 1000, 1, args=[name, "1.0", "0", module, "1.0", "0", "c0000005", "0x0", "1"])

        folder = "D:\\Data\\AppData\\Local\\CrashDumps"
        dumps = {"enabled": True, "folder": folder, "dumps": [
            {"name": "game.exe", "time": NOW - datetime.timedelta(days=1), "size": 40 * MB, "folder": folder},
            {"name": "game.exe", "time": NOW - datetime.timedelta(days=2), "size": 40 * MB, "folder": folder},
            {"name": "game.exe", "time": NOW - datetime.timedelta(days=40), "size": 40 * MB, "folder": folder},
            {"name": "other.exe", "time": NOW - datetime.timedelta(days=1), "size": 1 * MB, "folder": folder}]}
        finding = verdict("app_crashes", app_events=[crash("game.exe")], local_dumps=dumps)
        self.assertIn(("item_dumps_saved", {"name": "game.exe", "n": 2, "folder": folder, "size": Size(80 * MB)}),
                      finding.items)
        self.assertNotIn("other.exe", repr(finding.items), "dumps of a program that is not in the log are not listed")
        gpu = verdict("app_crashes", app_events=[crash("game.exe", "nvwgf2umx.dll")])
        self.assertIn(("item_shader_cache", {"folder": "%LocalAppData%\\NVIDIA\\DXCache"}), gpu.items)
        amd = verdict("app_crashes", app_events=[crash("game.exe", "amdxx64.dll")])
        self.assertIn(("item_shader_cache", {"folder": "%LocalAppData%\\AMD\\DxCache"}), amd.items)
        tdr = verdict("gpu_resets", events=[event("Display", 4101, level=3)])
        self.assertIn(("item_shader_cache", {"folder": "%LocalAppData%\\NVIDIA\\DXCache"}), tdr.items)
        self.assertRenders(finding)
        self.assertRenders(tdr)

    def test_crash_reports_outside_the_log(self):
        report = {"name": "Brave", "kind": "crashpad", "folder": "D:\\Data\\Crashpad\\reports", "recent": 3,
                  "total": 30, "newest": NOW - datetime.timedelta(days=1), "size": 3 * MB}
        finding = verdict("crash_files", crash_files=[report])
        self.assertEqual((finding.severity, finding.params["name"], finding.params["n"]), ("warning", "Brave", 3))
        self.assertEqual(finding.items[0][1]["n"], 3)
        self.assertIn(("item_crash_files_hidden", {}), finding.items)
        self.assertIn(("item_crash_files_tabs", {}), finding.items)
        self.assertEqual(finding.actions, [], "Reliability Monitor does not show these crashes")
        self.assertEqual(self.severity("crash_files", crash_files=[dict(report, recent=1)]), "info")
        self.assertEqual(self.severity("crash_files", crash_files=[dict(report, recent=0)]), "ok")
        wer = dict(report, name="game.exe", kind="wer", recent=1)
        queued = verdict("crash_files", crash_files=[wer])
        self.assertEqual(queued.actions, ["reliability"])
        self.assertNotIn(("item_crash_files_tabs", {}), queued.items)
        both = verdict("crash_files", crash_files=[wer, report])
        self.assertEqual((both.params["name"], both.params["n"]), ("Brave", 4))
        self.assertRenders(both)

    def test_live_kernel_dumps(self):
        day = datetime.timedelta(days=1)
        dump = {"component": "WATCHDOG", "time": NOW - 5 * day, "size": 2 * MB}
        finding = verdict("live_kernel", live_kernel={"readable": True, "dumps": [dump], "components": ["WATCHDOG"]})
        self.assertEqual((finding.severity, finding.params["n"]), ("warning", 1))
        self.assertEqual(finding.items[0][1]["kind"], "kind_live_watchdog")
        self.assertIn(("item_live_watchdog_hint", {}), finding.items)
        old = verdict("live_kernel", live_kernel={"readable": True, "dumps": [dict(dump, time=NOW - 90 * day)],
                                                  "components": ["WATCHDOG"]})
        self.assertEqual((old.severity, old.line, old.params["date"]), ("ok", "live_kernel_old", (NOW - 90 * day).date()))
        hidden = verdict("live_kernel", live_kernel={"readable": False, "dumps": [], "components": ["NDIS"]})
        self.assertEqual((hidden.severity, hidden.line), ("info", "live_kernel_registry"))
        self.assertEqual(verdict("live_kernel", live_kernel={"readable": False, "dumps": [], "components": []}).line,
                         "unknown_admin")
        mixed = verdict("live_kernel", wer_off=True, live_kernel={"readable": True, "components": [], "dumps": [
            dump, dict(dump, component="USBHUB3"), dict(dump, component="Mystery"), dict(dump, component="")]})
        kinds = {params["kind"] for key, params in mixed.items if key == "item_live_kind"}
        self.assertEqual(kinds, {"kind_live_watchdog", "kind_live_usb", "kind_live_other"})
        self.assertIn(("item_wer_off", {}), mixed.items)
        self.assertEqual(mixed.params["n"], 4)
        self.assertRenders(mixed)
        self.assertRenders(hidden)

    def test_programs_with_documented_problems(self):
        def software(programs=(), services=(), rtss=None, packages=()):
            return {"programs": {title.lower(): (title, version) for title, version in programs}, "packages": list(packages),
                    "services": {name.lower(): {"display": display, "start": start} for name, display, start in services},
                    "rtss": rtss}

        self.assertEqual(verdict("conflicting_software", software=software()).line, "conflicts_ok")
        inpout = verdict("conflicting_software", software=software(services=[("inpoutx64", "inpoutx64", 1)]))
        self.assertEqual((inpout.severity, inpout.items[0][0], inpout.actions), ("warning", "item_sw_inpout", ["devices"]))
        self.assertEqual(self.severity("conflicting_software", software=software(services=[("inpoutx64", "inpoutx64", 4)])),
                         "ok", "a disabled driver does not load")
        auto = software(services=[("NahimicService", "Nahimic service", 2)])
        nahimic = verdict("conflicting_software", software=auto)
        self.assertEqual((nahimic.severity, nahimic.items[0]), ("warning", ("item_sw_nahimic", {"name": "Nahimic service"})))
        manual = software(services=[("NahimicService", "Nahimic service", 3)])
        self.assertEqual(verdict("conflicting_software", software=manual).items[0][0], "item_sw_nahimic_installed")
        self.assertEqual(verdict("conflicting_software", software=manual, processes={"nahimicservice"}).items[0][0],
                         "item_sw_nahimic")
        sonic = verdict("conflicting_software", software=software(packages=["ASUSTeKCOMPUTERINC.SonicStudio3_1.0_x64__q"]))
        self.assertEqual(sonic.items, [("item_sw_nahimic_installed", {"name": "Sonic Studio"})])
        overwolf = verdict("conflicting_software", software=software(programs=[("Overwolf", "0.2"), ("OBS Studio", "30")],
                                                                     rtss=(7, 3, 5, 0)))
        self.assertEqual([key for key, _ in overwolf.items], ["item_sw_overwolf_rtss", "item_sw_overwolf_capture"])
        self.assertEqual((overwolf.severity, overwolf.items[0][1]["version"]), ("warning", "7.3.5"))
        self.assertEqual(self.severity("conflicting_software", software=software(programs=[("Overwolf", "0.2")],
                                                                                  rtss=(7, 3, 7, 0))), "ok")
        pups = verdict("conflicting_software", software=software(programs=[
            ("Advanced SystemCare 17", "17.0"), ("Restoro", "2.6"), ("Driver Booster 11", "11"), ("CCleaner", "6.20")]))
        self.assertEqual([key for key, _ in pups.items], ["item_sw_pup", "item_sw_scam", "item_sw_optimizer", "item_sw_ccleaner"])
        self.assertEqual((pups.severity, pups.params["n"], pups.actions), ("warning", 4, ["apps"]))
        machine = software(programs=[("VMware Workstation", "17.5")])
        slow = verdict("conflicting_software", software=machine, vbs={"available": [1, 2], "running": [2]})
        self.assertEqual((slow.severity, slow.items), ("info", [("item_sw_vmware_vbs", {"name": "VMware Workstation"})]))
        self.assertEqual(self.severity("conflicting_software", software=machine), "ok")
        logitech = software(programs=[("Logitech Gaming Software", "8.96.88"), ("Logitech G HUB", "2024.1")])
        self.assertEqual(verdict("conflicting_software", software=logitech).items[0][0], "item_sw_lgs_ghub")
        newer = software(programs=[("Logitech Gaming Software", "9.02.65"), ("Logitech G HUB", "2024.1")])
        self.assertEqual(self.severity("conflicting_software", software=newer), "ok")
        arc = [{"name": "Intel(R) Arc(TM) A770 Graphics", "inf": "oem9.inf", "version": "32.0.101.6000",
                "pnp": "PCI\\VEN_8086&DEV_56A0&SUBSYS_00000000\\3&1", "code": 0, "date": "2026-06-17T00:00:00"}]
        crate = software(programs=[("ARMOURY CRATE", "6.1")])
        self.assertEqual(verdict("conflicting_software", software=crate, video=arc).items[0][0], "item_sw_armoury_arc")
        self.assertEqual(self.severity("conflicting_software", software=crate), "ok", "no Arc, no documented conflict")
        network = software(services=[("Killer Network Service", "Killer Network Service", 2), ("cFosSpeedS", "cFosSpeed System Service", 2)])
        self.assertEqual([key for key, _ in verdict("conflicting_software", software=network).items],
                         ["item_sw_killer", "item_sw_cfos"])
        corsair = software(programs=[("Corsair Link 4", "4.9"), ("iCUE", "5.1")])
        self.assertEqual(verdict("conflicting_software", software=corsair).items[0][0], "item_sw_corsair_link")
        self.assertRenders(verdict("conflicting_software", software=network))
        self.assertRenders(pups)
        self.assertRenders(nahimic)

    def test_graphics_driver_crashes(self):
        self.assertEqual(self.severity("gpu_resets", events=[event("Display", 4101, level=3)]), "warning")
        tdr = [event("Display", 4101, level=3, minutes=10 * i) for i in range(3)]
        self.assertEqual(self.severity("gpu_resets", events=tdr), "problem")
        # One NVIDIA incident writes several errors in the same minute; a live kernel event of that minute is the same
        nvidia = [event("nvlddmkm", 13), event("nvlddmkm", 153), event("nvlddmkm", 153, days_ago=2)]
        hang = event("Windows Error Reporting", 1001, level=4, args=["", "", "LiveKernelEvent", "", "", "141"])
        finding = verdict("gpu_resets", nvidia_events=nvidia, live_events=[hang])
        self.assertEqual((finding.severity, finding.params["n"]), ("warning", 2))
        kinds = {p["kind"]: p["n"] for key, p in finding.items if key == "item_event_kind"}
        self.assertEqual(kinds, {"kind_nvidia": 2, "kind_gpu_hang": 1})
        exceptions = verdict("gpu_resets", nvidia_events=[event("nvlddmkm", 13, minutes=i) for i in range(3)])
        self.assertEqual((exceptions.severity, exceptions.line, exceptions.params["n"]), ("info", "gpu_exceptions", 3),
                         "graphics exceptions without a restart are often the program's own fault")
        other = event("Windows Error Reporting", 1001, level=4, args=["", "", "LiveKernelEvent", "", "", "1a1"])
        self.assertEqual(self.severity("gpu_resets", live_events=[other]), "ok", "not a graphics hang")
        self.assertIn(("item_wer_off", {}), verdict("gpu_resets", wer_off=True).items)

    def test_hardware_errors(self):
        whea = "Microsoft-Windows-WHEA-Logger"
        self.assertEqual(self.severity("whea", whea=[event(whea, 18, level=2)]), "problem")
        unstable = verdict("whea", whea=[event(whea, 19, level=3)])
        self.assertEqual((unstable.severity, unstable.line), ("warning", "whea_unstable"),
                         "corrected processor errors are a warning sign even when few")
        self.assertEqual(self.severity("whea", whea=[event(whea, 47, level=3)]), "warning")
        self.assertEqual(self.severity("whea", whea=[event(whea, 17, level=3)] * 2), "info")
        storm = [event(whea, 17, level=3, minutes=i) for i in range(150)]
        self.assertEqual(self.severity("whea", whea=storm), "warning", "a storm of PCI Express errors")

    def test_memory_test(self):
        results = "Microsoft-Windows-MemoryDiagnostics-Results"
        self.assertIsNone(verdict("memory_test"), "never tested")
        finding = verdict("memory_test", memory_tests=[event(results, 1201, days_ago=30, level=4),
                                                      event(results, 1202, days_ago=2)])
        self.assertEqual((finding.severity, finding.params["date"]), ("problem", datetime.date(2026, 10, 22)))
        self.assertEqual(self.severity("memory_test", memory_tests=[event(results, 1102, days_ago=30),
                                                                    event(results, 1101, days_ago=1, level=4)]),
                         "ok", "the latest test passed")

    def test_devices(self):
        finding = verdict("devices", devices=[{"name": "Wi-Fi", "code": 28}, {"name": "Card reader", "code": 22},
                                              {"name": "Old phone", "code": 45}])
        self.assertEqual((finding.severity, finding.params["n"], finding.line), ("warning", 1, "devices"))
        self.assertEqual(finding.items[0][1]["problem"], "code_28")
        self.assertEqual(verdict("devices", devices=[{"name": "Sound", "code": 12}]).line, "devices_conflict")
        self.assertEqual(verdict("devices", devices=[{"name": "X", "code": 99}]).items[0][1]["problem"], "code_other")

    def test_failing_services(self):
        scm = "Service Control Manager"
        failing = [event(scm, 7000, day % 6 + 1, args=["Windows Security Service", "%%577"]) for day in range(6)]
        once = [event(scm, 7023, args=["Network List Service"]), event(scm, 7031, 10, args=["Old Service"])]
        finding = verdict("services", service_events=failing + once)
        self.assertEqual((finding.severity, finding.params["n"]), ("warning", 1))
        self.assertEqual(finding.items, [("item_service", {"name": "Windows Security Service", "n": 6})])
        self.assertEqual(self.severity("services", service_events=once), "ok", "a single failure happens")
        noise = [event(scm, 7000, day, args=["luafv"]) for day in range(1, 7)] + \
            [event(scm, 7031, day, args=["Clipboard User Service_4a3b1"]) for day in range(1, 7)]
        self.assertEqual(self.severity("services", service_events=noise), "ok",
                         "UAC off is reported by itself, per-user services come and go")
        stopping = [event(scm, 7034, day, args=["Vendor Service"]) for day in range(1, 7)]
        shutdowns = [event("Microsoft-Windows-Kernel-General", 13, day, level=4, minutes=-1) for day in range(1, 7)]
        self.assertEqual(self.severity("services", service_events=stopping, shutdowns=shutdowns), "ok",
                         "stopping badly while Windows shuts down does no harm")
        self.assertEqual(self.severity("services", service_events=stopping), "warning")

    def test_disabled_services(self):
        found = [("BITS", "Background Intelligent Transfer Service", "updates")]
        finding = verdict("core_services", disabled_services=found)
        self.assertEqual((finding.severity, finding.items),
                         ("warning", [("item_service_off", {"name": "Background Intelligent Transfer Service",
                                                            "effect": "effect_updates"})]))
        self.assertRenders(finding)
        self.assertEqual(self.severity("core_services", disabled_services=[("WSearch", "Windows Search", "search")]),
                         "info", "search only gets slower")
        sysmain = [("SysMain", "SysMain", "compression")]
        self.assertEqual(self.severity("core_services", disabled_services=sysmain), "ok", "16 GB needs no compression")
        self.assertEqual(self.severity("core_services", disabled_services=sysmain,
                                       memory=dict(healthy()["memory"], total=8 * GB)), "info")

    def test_system_files_runtime_and_media(self):
        self.assertEqual(self.severity("system_files", image="Repairable"), "warning")
        self.assertEqual(self.severity("system_files", image="NonRepairable"), "problem")
        not_admin = verdict("system_files", image=None, admin=False)
        self.assertEqual((not_admin.severity, not_admin.line), ("unknown", "unknown_admin"))
        old = verdict("vc_runtime", vc_runtime={"x64": (14, 36, 32532, 0), "x86": (14, 50, 1, 0)})
        self.assertEqual((old.severity, old.line), ("warning", "runtime_old"))
        missing = verdict("vc_runtime", vc_runtime={"x64": (14, 50, 1, 0), "x86": None})
        self.assertEqual((missing.severity, missing.line), ("info", "runtime_missing"))
        self.assertRenders(missing)
        self.assertIsNone(verdict("media_pack"), "not an N edition")
        windows_n = dict(healthy()["windows"], edition="ProfessionalN", media=False)
        self.assertEqual(self.severity("media_pack", windows=windows_n), "warning")
        self.assertEqual(self.severity("media_pack", windows=dict(windows_n, media=True)), "ok")

    def test_battery(self):
        laptop = dict(healthy()["power"], battery=True)
        self.assertEqual(self.severity("battery", power=laptop, battery={"design": 50000, "full": 25000}), "warning")
        self.assertEqual(self.severity("battery", power=laptop, battery={"design": 50000, "full": 15000}), "problem")
        self.assertEqual(self.severity("battery", power=laptop, battery={"design": 50000, "full": 45000}), "ok")
        self.assertEqual(self.severity("battery", power=laptop), "unknown")

    def test_antivirus(self):
        off = {"name": "Windows Defender", "state": 0x60100}
        other = {"name": "Kaspersky", "state": 0x41000}
        self.assertTrue(diagnostics.antivirus_on(other["state"]))
        self.assertEqual(self.severity("antivirus", antivirus=[off]), "problem")
        self.assertEqual(self.severity("antivirus", antivirus=[]), "problem")
        self.assertEqual(self.severity("antivirus", antivirus=[off, other]), "ok", "Defender steps aside")
        many = verdict("antivirus", antivirus=[{"name": "Windows Defender", "state": 0x61100}, other])
        self.assertEqual((many.severity, many.params["names"]), ("warning", "Windows Defender, Kaspersky"))
        self.assertEqual(self.severity("antivirus", antivirus=[{"name": "Windows Defender", "state": 0x61110}]),
                         "warning")
        windows = dict(healthy()["windows"], server=True)
        self.assertIsNone(verdict("antivirus", windows=windows), "Windows Server has no Security Center")
        self.assertIsNone(verdict("antivirus", windows=windows, antivirus=None))

    def test_security_settings(self):
        finding = verdict("security_settings", security={"uac_off": True, "mitigations_off": True})
        self.assertEqual((finding.severity, [k for k, _ in finding.items], finding.actions),
                         ("warning", ["item_uac_off", "item_mitigations_off"], ["uac"]))
        boot = healthy()["boot"]
        on = dict(boot, integrity=diagnostics.CI_ENABLED | diagnostics.CI_HVCI)
        hvci = verdict("memory_integrity", boot=on)
        self.assertEqual((hvci.severity, hvci.items), ("info", []))
        old = verdict("memory_integrity", boot=on, vbs={"available": [1, 2, 3], "running": [2]})
        self.assertEqual(old.items, [("item_no_mbec", {})], "emulated on processors without MBEC")
        self.assertIsNone(verdict("memory_integrity"), "off: nothing to point out")

    def test_secure_boot(self):
        firmware = healthy()["firmware"]
        legacy = verdict("secure_boot", firmware=dict(firmware, uefi=False, secure_boot=None, tpm=0))
        self.assertEqual((legacy.severity, [k for k, _ in legacy.items]), ("info", ["item_legacy_boot",
                                                                                    "item_tpm_missing"]))
        self.assertEqual(self.severity("secure_boot", firmware=dict(firmware, secure_boot=False, anti_cheat=True)),
                         "warning", "Riot Vanguard will not start")
        self.assertEqual(self.severity("secure_boot", firmware=dict(firmware, tpm=None)), "unknown")

    def test_updates(self):
        self.assertEqual(self.severity("windows_update", update_settings={"disabled": True, "policy_off": False}),
                         "problem")
        self.assertEqual(self.severity("windows_update", update_settings={"disabled": False, "policy_off": True}),
                         "warning")
        self.assertEqual(self.severity("windows_update", windows_updated=NOW - datetime.timedelta(days=50)), "warning",
                         "the Store's installs moved the service's own date, the monthly update is what counts")
        self.assertEqual(self.severity("windows_update", windows_updated=NOW - datetime.timedelta(days=100)), "problem")
        self.assertEqual(self.severity("windows_update", windows_updated=None, last_update=None), "unknown")
        self.assertEqual(self.severity("windows_update", windows_updated=None,
                                       last_update=NOW - datetime.timedelta(days=60)), "warning",
                         "the service's date when the servicing store cannot be read")
        self.assertEqual(self.severity("pending_restart", restart_pending=True), "warning")
        client = "Microsoft-Windows-WindowsUpdateClient"
        cumulative = "2026-10 Cumulative Update for Windows 11 Version 25H2 for x64-based Systems (KB5127648)"
        failed = [event(client, 20, 5, args=["-2145124329", cumulative]), event(client, 20, 4, args=["-2145124329",
                                                                                                       cumulative])]
        finding = verdict("windows_update", update_events=failed)
        self.assertEqual((finding.severity, finding.line), ("warning", "wu_failed"))
        self.assertEqual(finding.items, [("item_update_failed", {"name": cumulative, "code": "0x80240017"})])
        self.assertEqual(self.severity("windows_update", update_events=failed[:1]), "ok", "one failure is retried")
        later = event(client, 19, 1, level=4, args=[cumulative.replace("2026-10", "2026-11").replace("27648", "31000")])
        self.assertEqual(self.severity("windows_update", update_events=failed + [later]), "ok",
                         "a newer update of the same kind went in")
        store = [event(client, 20, day, args=["-2147009278", "9N0DX20HK701-Microsoft.WindowsTerminal"])
                 for day in (1, 2)]
        self.assertEqual(self.severity("windows_update", update_events=store), "ok", "the Store retries by itself")
        defender = "Security Intelligence Update for Microsoft Defender Antivirus - KB2267602 (Version 1.461.171.0)"
        self.assertEqual(self.severity("windows_update", update_events=[event(client, 20, d, args=["-1", defender])
                                                                        for d in (1, 2)]), "ok",
                         "definitions update every few hours")
        self.assertEqual(diagnostics.update_family(cumulative), "cumulative update for windows 11 version 25h2 for "
                                                                "x64-based systems")

    def test_windows_support(self):
        def windows(build, edition="Professional", version=None):
            return {"product": "Windows 11" if build >= 22000 else "Windows 10", "version": version, "build": build,
                    "edition": edition, "update": 1000, "server": False, "media": True}

        finding = verdict("windows_support", windows=windows(26100, version="24H2"))
        self.assertEqual((finding.severity, finding.line, finding.params["date"]),
                         ("warning", "support_ended", datetime.date(2026, 10, 13)), "ended 11 days ago")
        later = NOW + datetime.timedelta(days=60)
        self.assertEqual(self.severity("windows_support", windows=windows(26100), now=later), "problem")
        self.assertEqual(self.severity("windows_support", windows=windows(26100, "Enterprise")), "ok")
        self.assertEqual(self.severity("windows_support", windows=windows(22631, "Education")), "warning",
                         "ends on 10 November 2026")
        win10 = verdict("windows_support", windows=windows(19045))
        self.assertEqual((win10.severity, win10.line), ("warning", "support_win10"),
                         "Extended Security Updates may still cover it")
        self.assertEqual(verdict("windows_support", windows=windows(26200)).params["windows"], "Windows 11 25H2")
        self.assertEqual(verdict("windows_support", windows=windows(28000)).params["windows"], "Windows 11 26H1")
        self.assertIsNone(verdict("windows_support", windows=windows(27950)), "an Insider build")
        self.assertIsNone(verdict("windows_support", windows=windows(19044, "EnterpriseS")), "LTSC")

    def test_network(self):
        conflict = event("Tcpip", 4199, 3, args=["", "192.168.1.20", "00-11-22-33-44-55"])
        finding = verdict("network", events=[conflict])
        self.assertEqual((finding.severity, finding.params["address"]), ("warning", "192.168.1.20"))
        self.assertEqual(self.severity("network", events=[dict(conflict, time=NOW - datetime.timedelta(days=40))]),
                         "ok")
        slow = verdict("network", adapters=[{"name": "Realtek PCIe GbE Family Controller", "speed": 100_000_000}])
        self.assertEqual((slow.severity, slow.params["speed"]), ("info", 100))

    def test_proxy_and_hosts(self):
        self.assertEqual(self.severity("proxy", proxy={"enabled": True, "server": "127.0.0.1:8080", "pac": ""}),
                         "warning")
        self.assertEqual(self.severity("proxy", proxy={"enabled": False, "server": "", "pac": "http://wpad/x.pac"}),
                         "warning")
        self.assertEqual(self.severity("proxy", proxy={"enabled": True, "server": "", "pac": ""}), "ok")
        finding = verdict("hosts", hosts={"entries": 3, "blocked": ["update.microsoft.com"]})
        self.assertEqual((finding.severity, finding.items), ("warning", [("item_name",
                                                                          {"name": "update.microsoft.com"})]))
        self.assertEqual(self.severity("hosts", hosts={"entries": 25000, "blocked": []}), "info")

    def test_one_broken_check_does_not_hide_the_others(self):
        facts = healthy()
        facts["memory"] = {"total": "?"}
        findings = {f.check: f.severity for f in diagnostics.evaluate(facts)}
        self.assertEqual(findings["ram_load"], "unknown")
        self.assertEqual(findings["crashes"], "ok")


LUID = "0x00000000_0x0000C5D4"


def tick(seconds=0, **changes):
    """One second of a quiet watch."""
    found = {"time": NOW + datetime.timedelta(seconds=seconds), "cpu": 8.0, "cpu_time": 10.0, "core_max": 40.0,
             "speed": 105.0, "interrupts": 0.4, "free_mb": 9000.0, "commit": 55.0, "pages_out": 0.0,
             "disks": {"0 C:": {"busy": 3.0, "ms": 0.2, "mbs": 1.0}}, "gpu": {LUID: {"load": 5.0, "dedicated_mb": 1500.0}},
             "temperature": 45, "passive": 100.0, "top_cpu": ("chrome.exe", 3.0), "top_io": ("chrome.exe", 0.4),
             "pause_ms": 4.0, "hung": []}
    found.update(changes)
    return found


def watch_facts(ticks=None, episodes=(), adapters=None):
    ticks = ticks if ticks is not None else [tick(i) for i in range(30)]
    if adapters is None:
        adapters = {LUID: {"name": CARD, "vram": 12 * GB, "software": False, "discrete": True}}
    return {"seconds": len(ticks), "ticks": ticks, "episodes": list(episodes), "adapters": adapters,
            "ram_mb": 16384.0, "missing": []}


def stress_facts(speeds=None, loads=None, passive=None, temperatures=None, n=60):
    speeds = speeds or [118.0] * n
    loads = loads or [97.0] * n
    passive = passive or [100.0] * n
    temperatures = temperatures or [None] * n
    return {"seconds": n, "threads": 16,
            "ticks": [{"load": loads[i], "speed": speeds[i], "temperature": temperatures[i], "passive": passive[i]}
                      for i in range(n)]}


def ping(lost=0.0, avg=12.0, worst=18.0, jitter=2.0):
    return {"sent": 60, "lost": lost, "avg": avg, "worst": worst, "jitter": jitter}


def connection_facts(router=None, one=None, two=None, dns_ms=30, wifi=None):
    return {"gateway": "192.168.1.1", "dns_ms": dns_ms, "wifi": wifi,
            "targets": {"192.168.1.1": router or ping(avg=1.0, worst=3.0, jitter=0.5), "1.1.1.1": one or ping(),
                        "8.8.8.8": two or ping(avg=13.0, worst=16.0, jitter=1.5)}}


def episode(name="game.exe", seconds=20, reading=None, **changes):
    found = {"pid": 4242, "name": name, "title": "Game", "start": NOW, "end": NOW + datetime.timedelta(seconds=seconds),
             "reading": reading or {"kind": "busy"}, "cpu": 40.0, "disk": ("0 C:", 12.0, 3.0), "free_mb": 8000.0}
    found.update(changes)
    return found


class LiveTests(unittest.TestCase):
    """The verdicts of the live tests on made-up readings."""

    def severity(self, check, **changes):
        return verdict(check, **changes).severity

    def assertRenders(self, finding):
        self.assertIsNotNone(finding)
        render_all([finding])
        return finding

    def test_nothing_known(self):
        for check in ("system_pauses", "hung_programs", "disk_latency", "memory_live", "cpu_live", "gpu_live",
                      "cpu_throttle", "disk_speed", "connection", "dead_shares"):
            self.assertEqual(verdict(check, **{k: None for k in ("watch", "stress", "disk_speed", "connection",
                                                                    "shares")}).severity, "unknown", check)

    def test_pauses_of_the_whole_system(self):
        ticks = [tick(i) for i in range(30)]
        ticks[5]["pause_ms"] = 820.0
        found = self.assertRenders(verdict("system_pauses", watch=watch_facts(ticks)))
        self.assertEqual((found.severity, found.line, found.params["n"], found.params["seconds"]), ("problem", "pauses_stall", 1, 0.8))
        self.assertEqual(found.items[0][0], "item_pause")
        self.assertEqual(found.items[0][1]["name"], "chrome.exe")
        ticks[5]["pause_ms"] = 160.0
        ticks[9]["pause_ms"] = 120.0
        found = self.assertRenders(verdict("system_pauses", watch=watch_facts(ticks)))
        self.assertEqual((found.severity, found.line, found.params["n"], found.params["ms"]), ("warning", "pauses_hitch", 2, 160))
        # Drivers that keep the processor busy with interrupts, without a pause
        ticks = [tick(i, interrupts=6.0) for i in range(30)]
        found = self.assertRenders(verdict("system_pauses", watch=watch_facts(ticks)))
        self.assertEqual((found.severity, found.line), ("warning", "interrupts_watch"))
        self.assertEqual(found.items[-1][0], "item_interrupts_watch")
        ticks = [tick(i) for i in range(30)]
        ticks[3]["interrupts"] = 30.0  # one second of storm counts too
        self.assertEqual(verdict("system_pauses", watch=watch_facts(ticks)).line, "interrupts_watch")
        self.assertEqual(self.severity("system_pauses"), "ok")

    def test_processor_during_the_watch(self):
        self.assertEqual(verdict("cpu_live").line, "cpu_watch_ok")
        cooled = [tick(i, passive=80.0 if i < 4 else 100.0) for i in range(30)]
        found = self.assertRenders(verdict("cpu_live", watch=watch_facts(cooled)))
        self.assertEqual((found.severity, found.line, found.params["seconds"], found.params["limit"]), ("warning", "cpu_watch_cooling", 4, 80))
        slow = [tick(i, cpu_time=70.0, speed=45.0) for i in range(30)]
        found = self.assertRenders(verdict("cpu_live", watch=watch_facts(slow)))
        self.assertEqual((found.severity, found.line, found.params["percent"]), ("warning", "cpu_watch_slow", 45))
        full = [tick(i, cpu=95.0, top_cpu=("game.exe", 80.0) if i % 3 else ("steam.exe", 10.0)) for i in range(30)]
        found = self.assertRenders(verdict("cpu_live", watch=watch_facts(full)))
        self.assertEqual((found.severity, found.line, found.params["seconds"]), ("warning", "cpu_watch_full", 30))
        self.assertEqual(found.items[0], ("item_mostly", {"name": "game.exe"}))
        one = [tick(i, core_max=99.0, cpu=12.0, top_cpu=("old game.exe", 5.0)) for i in range(30)]
        found = self.assertRenders(verdict("cpu_live", watch=watch_facts(one)))
        self.assertEqual((found.severity, found.line), ("info", "cpu_watch_one_core"))
        # A drop from turbo under load is a note on an otherwise fine processor
        turbo = [tick(i, cpu_time=60.0, speed=130.0 if i < 10 else 70.0) for i in range(30)]
        found = self.assertRenders(verdict("cpu_live", watch=watch_facts(turbo)))
        self.assertEqual(found.severity, "ok")
        self.assertIn("item_turbo_drop", [key for key, _ in found.items])

    def test_memory_during_the_watch(self):
        self.assertEqual(verdict("memory_live").line, "memory_watch_ok")
        low = [tick(i, free_mb=250.0 if i == 12 else 9000.0, pages_out=5000.0 if i in (12, 13) else 0.0)
               for i in range(30)]
        found = self.assertRenders(verdict("memory_live", watch=watch_facts(low)))
        self.assertEqual((found.severity, found.line), ("problem", "memory_watch_out"))
        self.assertEqual(found.items, [("item_paging", {"seconds": 2})])
        self.assertEqual(verdict("memory_live", watch=watch_facts([tick(i, commit=96.0) for i in range(30)])).severity, "problem")
        tight = [tick(i, free_mb=1000.0) for i in range(30)]  # 6% of 16 GB
        self.assertEqual(verdict("memory_live", watch=watch_facts(tight)).line, "memory_watch_tight")
        self.assertEqual(verdict("memory_live", watch=watch_facts([tick(i, commit=91.0) for i in range(30)])).line, "memory_watch_tight")

    def test_drives_during_the_watch(self):
        self.assertEqual(verdict("disk_latency").line, "disk_watch_ok")
        late = [tick(i) for i in range(30)]
        for i in (4, 5, 6):
            late[i]["disks"]["0 C:"] = {"busy": 100.0, "ms": 350.0, "mbs": 0.5}
            late[i]["top_io"] = ("msmpeng.exe", 2.0)
        found = self.assertRenders(verdict("disk_latency", watch=watch_facts(late)))
        self.assertEqual((found.severity, found.line, found.params["name"], found.params["seconds"]), ("problem", "disk_watch_late", "C: (disk 0)", 3))
        self.assertEqual([key for key, _ in found.items], ["item_disk_who", "item_disk_idle_slow", "item_first_at"])
        self.assertEqual(found.items[0][1]["name"], "msmpeng.exe")
        self.assertEqual(found.items[1][1]["seconds"], 3)
        once = [tick(i) for i in range(30)]
        once[7]["disks"]["0 C:"] = {"busy": 50.0, "ms": 1500.0, "mbs": 20.0}  # one answer above a second is enough
        self.assertEqual(verdict("disk_latency", watch=watch_facts(once)).severity, "problem")
        full = [tick(i) for i in range(30)]
        for i in range(8):
            full[i]["disks"]["0 C:"] = {"busy": 97.0, "ms": 15.0, "mbs": 120.0}
        found = self.assertRenders(verdict("disk_latency", watch=watch_facts(full)))
        self.assertEqual((found.severity, found.line, found.params["seconds"]), ("warning", "disk_watch_full", 8))
        # Two drives: the worse one speaks
        two = [tick(i) for i in range(30)]
        for t in two:
            t["disks"]["1 D:"] = {"busy": 98.0, "ms": 20.0, "mbs": 100.0}
        two[3]["disks"]["0 C:"] = {"busy": 90.0, "ms": 1200.0, "mbs": 1.0}
        found = verdict("disk_latency", watch=watch_facts(two))
        self.assertEqual((found.severity, found.params["name"]), ("problem", "C: (disk 0)"))
        self.assertEqual(verdict("disk_latency", watch=watch_facts([tick(i, disks={}) for i in range(30)])).severity, "unknown")

    def test_graphics_during_the_watch(self):
        found = self.assertRenders(verdict("gpu_live"))
        self.assertEqual((found.severity, found.line, found.params["name"]), ("ok", "gpu_watch_ok", CARD))
        full = [tick(i, gpu={LUID: {"load": 60.0, "dedicated_mb": 11.9 * 1024}}) for i in range(30)]
        found = self.assertRenders(verdict("gpu_live", watch=watch_facts(full)))
        self.assertEqual((found.severity, found.line), ("warning", "vram_full"))
        self.assertEqual(found.items, [("item_gpu", found.params)])
        maxed = [tick(i, gpu={LUID: {"load": 99.0, "dedicated_mb": 6000.0}}) for i in range(30)]
        found = self.assertRenders(verdict("gpu_live", watch=watch_facts(maxed)))
        self.assertEqual((found.severity, found.line, found.params["seconds"]), ("info", "gpu_watch_limit", 30))
        # The software adapter never speaks; a PC without graphics counters has nothing to say
        software = {"0x00000000_0x0000ED5D": {"name": "Microsoft Basic Render Driver", "vram": 0, "software": True,
                                              "discrete": False}}
        self.assertIsNone(verdict("gpu_live", watch=watch_facts(adapters=software)))
        self.assertIsNone(verdict("gpu_live", watch=watch_facts([tick(i, gpu={}) for i in range(30)])))

    def test_programs_that_stopped_responding(self):
        found = self.assertRenders(verdict("hung_programs"))
        self.assertEqual((found.severity, found.line), ("ok", "hung_ok"))
        found = self.assertRenders(verdict("hung_programs", watch=watch_facts(episodes=[episode(seconds=20)])))
        self.assertEqual((found.severity, found.params["n"], found.params["name"], found.params["seconds"]), ("problem", 1, "game.exe", 25))
        self.assertEqual([key for key, _ in found.items], ["item_hung", "item_chain_busy", "item_hung_system", "item_hung_disk"])
        self.assertEqual(found.items[3][1], {"name": "C: (disk 0)", "busy": 12, "ms": 3})
        found = verdict("hung_programs", watch=watch_facts(episodes=[episode(seconds=3, disk=None)]))
        self.assertEqual((found.severity, found.params["seconds"]), ("warning", 8))
        self.assertNotIn("item_hung_disk", [key for key, _ in found.items])
        # Every reading has its words
        for kind in ("deadlock", "other_program", "share", "network", "busy", "own_thread", "blocked", "unknown",
                     "unreadable"):
            reading = {"kind": kind, "name": "spoolsv.exe", "pid": 1234, "objects": "critical section, mutex"}
            found = self.assertRenders(verdict("hung_programs", watch=watch_facts(episodes=[episode(reading=reading)])))
            self.assertIn(("item_chain_" + kind), [key for key, _ in found.items])

    def test_wait_chain_readings(self):
        names = {100: "game.exe", 200: "spoolsv.exe"}
        thread = lambda pid, status="blocked": {"kind": "thread", "status": status, "pid": pid, "tid": 1}
        self.assertEqual(diagnostics.chain_reading(None, 100, names)["kind"], "unreadable")
        self.assertEqual(diagnostics.chain_reading({"nodes": [thread(100)], "cycle": True}, 100, names)["kind"], "deadlock")
        chain = {"nodes": [thread(100), {"kind": "alpc", "status": "owned", "name": ""}, thread(200, "running")], "cycle": False}
        self.assertEqual(diagnostics.chain_reading(chain, 100, names), {"kind": "other_program", "pid": 200, "name": "spoolsv.exe"})
        chain = {"nodes": [thread(100), {"kind": "share", "status": "blocked", "name": "\\\\nas\\files"}], "cycle": False}
        self.assertEqual(diagnostics.chain_reading(chain, 100, names)["kind"], "share")
        chain = {"nodes": [thread(100), {"kind": "socket", "status": "blocked", "name": ""}], "cycle": False}
        self.assertEqual(diagnostics.chain_reading(chain, 100, names)["kind"], "network")
        self.assertEqual(diagnostics.chain_reading({"nodes": [thread(100, "running")], "cycle": False}, 100, names)["kind"], "busy")
        chain = {"nodes": [thread(100), {"kind": "critical_section", "status": "owned", "name": ""}, thread(100, "running")], "cycle": False}
        self.assertEqual(diagnostics.chain_reading(chain, 100, names)["kind"], "own_thread")
        chain = {"nodes": [thread(100), {"kind": "critical_section", "status": "owned", "name": ""}, thread(100)], "cycle": False}
        self.assertEqual(diagnostics.chain_reading(chain, 100, names), {"kind": "blocked", "objects": "critical section"})
        self.assertEqual(diagnostics.chain_reading({"nodes": [thread(100)], "cycle": False}, 100, names)["kind"], "unknown")

    def test_processor_under_full_load(self):
        found = self.assertRenders(verdict("cpu_throttle"))
        self.assertEqual((found.severity, found.line, found.params["start"], found.params["end"]), ("ok", "throttle_ok", 118, 118))
        self.assertEqual([key for key, _ in found.items], ["item_stress_load", "item_stress_no_temperature"])
        fading = [120.0] * 10 + [85.0] * 50  # a drop of 29%
        found = self.assertRenders(verdict("cpu_throttle", stress=stress_facts(fading, temperatures=[50 + i // 3 for i in range(60)])))
        self.assertEqual((found.severity, found.line, found.params["drop"]), ("warning", "throttle_fades", 29))
        self.assertIn("item_stress_temperature", [key for key, _ in found.items])
        settling = [120.0] * 10 + [103.0] * 50  # 14%
        found = self.assertRenders(verdict("cpu_throttle", stress=stress_facts(settling)))
        self.assertEqual((found.severity, found.line), ("info", "throttle_settles"))
        held = [55.0] * 60
        found = self.assertRenders(verdict("cpu_throttle", stress=stress_facts(held)))
        self.assertEqual((found.severity, found.line, found.params["end"]), ("warning", "throttle_held_back", 55))
        cooled = stress_facts(passive=[100.0] * 40 + [60.0] * 20)
        found = self.assertRenders(verdict("cpu_throttle", stress=cooled))
        self.assertEqual((found.severity, found.line, found.params["seconds"]), ("warning", "throttle_cooling", 20))
        light = stress_facts(loads=[40.0] * 60)
        found = self.assertRenders(verdict("cpu_throttle", stress=light))
        self.assertEqual((found.severity, found.line), ("info", "throttle_light"))
        # On battery a laptop is held back by design: the same readings are a note
        battery = dict(healthy()["power"], battery=True, plugged=False)
        found = self.assertRenders(verdict("cpu_throttle", stress=stress_facts(held), power=battery))
        self.assertEqual((found.severity, found.line), ("info", "throttle_held_back"))
        self.assertIn("item_on_battery", [key for key, _ in found.items])
        self.assertEqual(verdict("cpu_throttle", stress=stress_facts(n=5)).severity, "unknown")
        self.assertIsNone(verdict("cpu_throttle", stress=None, model="VMware, Inc. VMware Virtual Platform"))

    def test_drive_speed(self):
        found = self.assertRenders(verdict("disk_speed"))
        self.assertEqual((found.severity, found.line, found.params["cls"], found.params["name"]), ("ok", "speed_ok", "class_nvme", "Samsung SSD 980"))
        self.assertEqual([key for key, _ in found.items], ["item_speed_read", "item_speed_random"])
        reading = lambda seq, ms, source="files": {"sequential": seq, "random_ms": ms, "random_p95": ms * 2, "read_mb": 340, "source": source}
        found = self.assertRenders(verdict("disk_speed", disk_speed=reading(45.0, 12.0)))
        self.assertEqual((found.severity, found.line, found.items[0][0]), ("warning", "speed_very_slow", "item_speed_read_files"))
        self.assertEqual(verdict("disk_speed", disk_speed=reading(480.0, 9.0)).line, "ssd_slow")  # by latency
        self.assertEqual(verdict("disk_speed", disk_speed=reading(120.0, 0.3)).line, "ssd_slow")  # by throughput
        found = self.assertRenders(verdict("disk_speed", disk_speed=reading(420.0, 0.2)))
        self.assertEqual((found.severity, found.line, found.params["cls"]), ("info", "nvme_below_class", "class_sata"))
        hdd = [{"id": "0", "name": "WDC WD10EZEX", "media": "HDD", "health": "Healthy", "bus": "SATA"}]
        found = self.assertRenders(verdict("disk_speed", disks=hdd, disk_speed=reading(140.0, 11.0)))
        self.assertEqual((found.severity, found.line, found.params["cls"]), ("ok", "speed_ok", "class_hdd"))
        sata = [{"id": "0", "name": "Crucial MX500", "media": "SSD", "health": "Healthy", "bus": "SATA"}]
        self.assertEqual(verdict("disk_speed", disks=sata, disk_speed=reading(520.0, 0.2)).line, "speed_ok")
        self.assertEqual(verdict("disk_speed", disk_speed=None, admin=False).line, "unknown_admin")
        self.assertEqual(verdict("disk_speed", disk_speed=None).line, "unknown_read")

    def test_connection(self):
        found = self.assertRenders(verdict("connection"))
        self.assertEqual((found.severity, found.line, found.params), ("ok", "connection_ok", {"avg": 12, "worst": 16, "loss": 0}))
        self.assertEqual([key for key, _ in found.items], ["item_ping"] * 3 + ["item_dns_ok"])
        self.assertEqual(found.items[0][1]["name"], "ping_router")
        found = self.assertRenders(verdict("connection", connection={"gateway": None, "targets": {}, "dns_ms": None, "wifi": None}))
        self.assertEqual((found.severity, found.line), ("info", "connection_offline"))
        shaky = connection_facts(router=ping(lost=5.0, avg=4.0, worst=180.0, jitter=25.0), wifi=72)
        found = self.assertRenders(verdict("connection", connection=shaky))
        self.assertEqual((found.severity, found.line, found.params["loss"]), ("warning", "router_unstable", 5))
        self.assertEqual([key for key, _ in found.items][-2:], ["item_dns_ok", "item_home_wifi"])
        self.assertIn("item_wifi_signal", [key for key, _ in found.items])
        self.assertEqual(verdict("connection", connection=connection_facts(router=ping(jitter=16.0))).items[-1][0], "item_home_cable")
        line = connection_facts(one=ping(lost=4.0, jitter=30.0, worst=400.0), two=ping(lost=3.0, jitter=25.0, worst=350.0))
        found = self.assertRenders(verdict("connection", connection=line))
        self.assertEqual((found.severity, found.line, found.params), ("warning", "line_unstable", {"loss": 3, "jitter": 25.0, "worst": 350}))
        self.assertEqual(found.items[-1][0], "item_line")
        # One good internet address is enough: the other resolver may just be far away
        self.assertEqual(verdict("connection", connection=connection_facts(one=ping(lost=50.0, jitter=80.0, worst=900.0))).severity, "ok")
        found = self.assertRenders(verdict("connection", connection=connection_facts(dns_ms=None)))
        self.assertEqual((found.severity, found.line), ("warning", "dns_failed"))
        found = self.assertRenders(verdict("connection", connection=connection_facts(dns_ms=900)))
        self.assertEqual((found.severity, found.items[-1][0]), ("ok", "item_dns_slow"))
        found = self.assertRenders(verdict("connection", connection=connection_facts(wifi=35)))
        self.assertEqual((found.severity, found.line, found.params["percent"]), ("warning", "wifi_weak", 35))
        silent = connection_facts(router=ping(lost=100.0, avg=0.0, worst=0.0, jitter=0.0))
        found = self.assertRenders(verdict("connection", connection=silent))
        self.assertEqual((found.severity, found.line, found.params["avg"]), ("info", "router_silent", 12))

    def test_ping_statistics(self):
        self.assertIsNone(diagnostics.ping_stats([]))
        stats = diagnostics.ping_stats([10, None, 14, 12, None])
        self.assertEqual((stats["sent"], stats["lost"], stats["avg"], stats["worst"]), (5, 40.0, 12.0, 14))
        self.assertAlmostEqual(stats["jitter"], 3.0)  # |10-14| and |14-12| over two steps
        self.assertEqual(diagnostics.ping_stats([None, None])["lost"], 100.0)
        self.assertEqual(diagnostics.ping_stats([7])["jitter"], 0.0)

    def test_mapped_network_drives(self):
        self.assertIsNone(verdict("dead_shares"))
        shares = [{"drive": "Z:", "remote": "\\\\nas\\files", "alive": True}, {"drive": "Y:", "remote": "\\\\oldpc\\share", "alive": False}]
        found = self.assertRenders(verdict("dead_shares", shares=shares))
        self.assertEqual((found.severity, found.line, found.params), ("warning", "shares_dead", {"n": 1, "total": 2}))
        self.assertEqual([key for key, _ in found.items], ["item_share_ok", "item_share_dead"])
        found = self.assertRenders(verdict("dead_shares", shares=shares[:1]))
        self.assertEqual((found.severity, found.line), ("ok", "shares_ok"))

    def test_helpers(self):
        self.assertEqual(diagnostics._disk_label("0 C: A:"), "C: A: (disk 0)")
        self.assertEqual(diagnostics._disk_label("_Total"), "disk _Total")
        self.assertEqual(diagnostics._most_common(["a", "b", "a", None]), "a")
        self.assertEqual(diagnostics._most_common([]), "?")
        self.assertEqual(diagnostics.busiest_disk(tick(disks={"0 C:": {"busy": 3.0, "ms": 1.0, "mbs": 0}, "1 D:": {"busy": 40.0, "ms": 9.0, "mbs": 0}})), ("1 D:", 40.0, 9.0))
        self.assertIsNone(diagnostics.busiest_disk(tick(disks={})))


class FakeSampler(diagnostics.Sampler):
    """A sampler over made-up counter readings: the parsing is tested without the counters."""

    def __init__(self, values=None, arrays=None):  # noqa: the real one opens a query
        self.values, self.arrays, self.missing, self.names, self.cores = values or {}, arrays or {}, [], {}, 8

    def value(self, key):
        return self.values.get(key)

    def array(self, key):
        return self.arrays.get(key, {})


class LiveReadings(unittest.TestCase):
    """What the live tests make of the raw counters, windows and chains, on made-up and on real readings."""

    def test_graphics_counters_are_summed_per_adapter(self):
        luid, other = "0x00000000_0x0000C5D4", "0x00000000_0x0000ED8B"
        arrays = {"gpu_memory": {f"luid_{luid}_phys_0": 3 * GB, f"luid_{other}_phys_0": 0.0},
                  "gpu": {f"pid_100_luid_{luid}_phys_0_eng_0_engtype_3D": 30.0,  # two programs on the 3D engine
                          f"pid_200_luid_{luid}_phys_0_eng_0_engtype_3D": 25.0,
                          f"pid_100_luid_{luid}_phys_0_eng_4_engtype_Copy": 70.0,  # the busiest engine counts
                          f"pid_300_luid_{other}_phys_0_eng_0_engtype_3D": 0.0,  # idle engines are skipped
                          "garbage": 50.0}}
        found = FakeSampler(arrays=arrays).gpu()
        self.assertEqual(found[luid], {"load": 70.0, "dedicated_mb": 3 * 1024})
        self.assertEqual(found[other], {"load": 0.0, "dedicated_mb": 0.0})
        self.assertEqual(FakeSampler().gpu(), {})

    def test_busiest_programs(self):
        arrays = {"process_id": {"_Total": 0, "Idle": 0, "chrome": 100, "chrome#1": 101, "SimpleTool": 999, "game": 300},
                  "process_cpu": {"_Total": 800.0, "Idle": 500.0, "chrome": 80.0, "chrome#1": 40.0, "SimpleTool": 700.0,
                                  "game": 240.0},
                  "process_io": {"chrome": 2 * MB, "chrome#1": 50 * MB, "SimpleTool": 900 * MB, "game": 1 * MB}}
        sampler = FakeSampler(arrays=arrays)
        top_cpu, top_io = sampler.processes(own_pid=999)
        self.assertEqual(top_cpu, ("game.exe", 30.0))  # 240% of one core over 8 cores; SimpleTool itself left out
        self.assertEqual(top_io, ("chrome.exe", 50.0))  # the "#1" copy counts under the program's name
        self.assertEqual(sampler.names, {100: "chrome.exe", 101: "chrome.exe", 999: "simpletool.exe", 300: "game.exe"})
        self.assertEqual(FakeSampler().processes(1), (None, None))

    def test_thermal_zones(self):
        self.assertEqual(FakeSampler(arrays={"temperature_fine": {"\\_TZ.TZ00": 3181.5, "\\_TZ.TZ01": 3010.0},
                                             "passive": {"\\_TZ.TZ00": 100.0, "\\_TZ.TZ01": 70.0}}).thermal(), (45, 70.0))
        self.assertEqual(FakeSampler(arrays={"temperature": {"\\_TZ.TZ00": 301.0}}).thermal(), (28, None))
        self.assertEqual(FakeSampler(arrays={"temperature": {"\\_TZ.TZ00": 0.0}}).thermal(), (None, None))
        self.assertEqual(FakeSampler().thermal(), (None, None))

    def test_a_tick_without_counters_says_none(self):
        tick_ = FakeSampler().tick(own_pid=1)
        for key in ("cpu", "cpu_time", "core_max", "speed", "interrupts", "free_mb", "commit", "pages_out",
                    "temperature", "passive", "top_cpu", "top_io"):
            self.assertIsNone(tick_[key], key)
        self.assertEqual((tick_["disks"], tick_["gpu"]), ({}, {}))
        self.assertIsInstance(tick_["time"], datetime.datetime)

    def test_a_tick_turns_counters_into_plain_values(self):
        values = {"cpu_time": 12.0, "cpu": 130.0, "speed": 121.0, "dpc": 0.4, "interrupt": 0.3, "free": 16000.0,
                  "commit": 70.0, "pages_out": 5.0}
        arrays = {"cores": {"0,0": 97.0, "0,1": 3.0, "0,_Total": 50.0, "_Total": 50.0},
                  "disk_idle": {"0 C:": 40.0, "1 D:": 100.0, "_Total": 70.0},
                  "disk_ms": {"0 C:": 0.012, "1 D:": 0.0}, "disk_bytes": {"0 C:": 20 * MB}}
        tick_ = FakeSampler(values, arrays).tick(own_pid=1)
        self.assertEqual((tick_["cpu"], tick_["cpu_time"], tick_["core_max"]), (100.0, 12.0, 97.0))  # utility capped
        self.assertAlmostEqual(tick_["interrupts"], 0.7)
        self.assertEqual(tick_["disks"]["0 C:"], {"busy": 60.0, "ms": 12.0, "mbs": 20.0})
        self.assertEqual(tick_["disks"]["1 D:"], {"busy": 0.0, "ms": 0.0, "mbs": 0.0})
        self.assertNotIn("_Total", tick_["disks"])
        self.assertEqual(FakeSampler({"cpu_time": 55.0}).tick(1)["cpu"], 55.0)  # no utility counter: time instead

    def test_the_real_counters_open_and_read(self):
        sampler = diagnostics.Sampler()
        try:
            self.assertEqual(sampler.missing, [])
            self.assertTrue(sampler.collect())
            time.sleep(0.3)
            self.assertTrue(sampler.collect())
            tick_ = sampler.tick(os.getpid())
            self.assertTrue(0 <= tick_["cpu"] <= 100)
            self.assertGreater(tick_["speed"], 10)
            self.assertGreater(tick_["free_mb"], 100)
            self.assertTrue(tick_["disks"])
            self.assertNotIn(os.getpid(), [None])
            self.assertIn(os.getpid(), sampler.names)
            self.assertNotEqual((tick_["top_cpu"] or ("", 0))[0], sampler.names[os.getpid()], "SimpleTool itself is left out")
        finally:
            sampler.close()
        stress = diagnostics.Sampler(diagnostics.STRESS_COUNTERS)
        try:
            self.assertEqual(set(stress.counters), set(diagnostics.STRESS_COUNTERS) - set(stress.missing))
        finally:
            stress.close()

    def test_the_pause_watch_measures_its_own_delay(self):
        pause = diagnostics._PauseWatch()
        pause.start()
        try:
            time.sleep(0.5)
            first = pause.pop()
            self.assertGreaterEqual(first, 0.0)
            self.assertLess(first, diagnostics.PAUSE_STALL_MS)
            self.assertLess(pause.pop(), first + 50, "pop() starts a new count")
        finally:
            pause.stop()
            pause.join(timeout=2)
        self.assertFalse(pause.is_alive())

    def test_a_frozen_window_is_caught_with_its_program(self):
        """A window that stops handling messages: Windows marks it after five seconds, the watch names the program
        once (not the ghost copy the desktop manager draws) and reads what it waits for."""
        code = ("import tkinter, time; r = tkinter.Tk(); r.title('SimpleTool test: frozen window'); r.update(); "
                "time.sleep(14)")
        child = subprocess.Popen([sys.executable, "-c", code])
        try:
            time.sleep(7)
            hung = diagnostics.hung_windows()
            self.assertEqual([title for pid, _, title in hung if pid == child.pid], ["SimpleTool test: frozen window"])
            watched = diagnostics.watch(2)
        finally:
            child.wait(timeout=20)
        episodes = [e for e in watched["episodes"] if e["pid"] == child.pid]
        self.assertEqual(len(episodes), 1)
        self.assertEqual(episodes[0]["name"], os.path.basename(sys.executable).lower())
        self.assertEqual(episodes[0]["title"], "SimpleTool test: frozen window")
        self.assertIn(episodes[0]["reading"]["kind"], ("busy", "unknown", "blocked"))  # asleep, not waiting on a lock
        self.assertNotIn("dwm.exe", [e["name"] for e in watched["episodes"]])
        self.assertTrue(all(child.pid in t["hung"] for t in watched["ticks"]))
        finding = diagnostics.check_hung_programs({"watch": watched})
        self.assertEqual((finding.severity, finding.params["name"]), ("warning", episodes[0]["name"]))
        render_all([finding])
        self.assertEqual([pid for pid, _, _ in diagnostics.hung_windows() if pid == child.pid], [])

    def test_the_wait_chain_follows_a_mutex_to_another_program(self):
        """Another process holds a named mutex and this one's thread waits for it: the chain names that process."""
        name = f"SimpleToolTest-{os.getpid()}-{uuid.uuid4().hex[:8]}"
        code = (f"import ctypes, time; k = ctypes.windll.kernel32; h = k.CreateMutexW(None, True, {name!r}); "
                "print('held', flush=True); time.sleep(10)")
        child = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(), "held")
            kernel32 = ctypes.windll.kernel32
            kernel32.OpenMutexW.restype = wintypes.HANDLE
            handle = kernel32.OpenMutexW(0x100000, False, name)  # SYNCHRONIZE
            self.assertTrue(handle)
            waiter = threading.Thread(target=kernel32.WaitForSingleObject, args=(handle, 8000), daemon=True)
            waiter.start()
            time.sleep(0.5)
            chain = diagnostics.wait_chain(waiter.native_id)
            self.assertIsNotNone(chain)
            kinds = [node["kind"] for node in chain["nodes"]]
            self.assertEqual(kinds[:2], ["thread", "mutex"])
            self.assertEqual(chain["nodes"][-1], {"kind": "thread", "status": "blocked", "pid": child.pid,
                                                  "tid": chain["nodes"][-1]["tid"]})
            reading = diagnostics.chain_reading(chain, os.getpid(), {child.pid: "python.exe"})
            self.assertEqual(reading, {"kind": "other_program", "pid": child.pid, "name": "python.exe"})
            # A thread that is working waits for nothing
            busy = diagnostics.wait_chain(threading.main_thread().native_id)
            self.assertEqual(diagnostics.chain_reading(busy, os.getpid(), {})["kind"], "busy")
        finally:
            child.kill()
            child.wait(timeout=10)
            child.stdout.close()
        waiter.join(timeout=10)
        kernel32.CloseHandle(handle)
        self.assertIsNone(diagnostics.wait_chain(0xFFFFFFF0), "no such thread: no chain")
        self.assertIsInstance(diagnostics.enable_debug_privilege(), bool)

    def test_reads_past_the_cache(self):
        """A temporary file read as the drive would be without administrator rights: the figures are real."""
        path = os.path.join(tempfile.gettempdir(), f"simpletool-read-{os.getpid()}.bin")
        size = 48 * MB
        with open(path, "wb") as f:
            f.write(os.urandom(size))
        kernel32 = diagnostics._disk_api()
        kernel32.SetFilePointerEx.argtypes = [wintypes.HANDLE, ctypes.c_longlong, ctypes.POINTER(ctypes.c_longlong),
                                              wintypes.DWORD]
        buffer = kernel32.VirtualAlloc(None, diagnostics.READ_CHUNK, 0x3000, 0x04)
        handle = kernel32.CreateFileW(path, diagnostics.GENERIC_READ, 7, None, 3, diagnostics.FILE_FLAG_NO_BUFFERING,
                                      None)
        try:
            self.assertTrue(handle and handle != wintypes.HANDLE(-1).value)
            with mock.patch.object(diagnostics, "RANDOM_READS", 20):
                found = diagnostics.measure_reads(kernel32, [(handle, size)], buffer, "files")
        finally:
            kernel32.CloseHandle(handle)
            kernel32.VirtualFree(buffer, 0, 0x8000)
            os.remove(path)
        self.assertEqual(found["source"], "files")
        self.assertEqual(found["read_mb"], 48)  # whole chunks of 4 MB
        self.assertGreater(found["sequential"], 1)
        self.assertGreater(found["random_ms"], 0)
        self.assertGreaterEqual(found["random_p95"], found["random_ms"] * 0.5)

    def test_large_files_of_windows_are_plain(self):
        for path, size in diagnostics.large_files():
            self.assertGreaterEqual(size, diagnostics.LARGE_FILE_MIN)
            self.assertTrue(path.lower().startswith(os.environ["SystemRoot"].lower()))
            self.assertFalse(os.stat(path).st_file_attributes & 0xA00, path)
        self.assertLessEqual(sum(size for _, size in diagnostics.large_files()[:-1]), diagnostics.LARGE_FILES_TOTAL)

    def test_drive_speed_without_rights_falls_back_to_files(self):
        with mock.patch.object(diagnostics, "large_files", lambda: []):
            self.assertIsNone(diagnostics.disk_speed(diagnostics.system_disk(), admin=False))
        with mock.patch.object(diagnostics, "measure_reads", lambda k, s, b, source: {"source": source, "n": len(s)}):
            with mock.patch.object(diagnostics, "large_files", lambda: [(sys.executable, os.path.getsize(sys.executable))]):
                self.assertEqual(diagnostics.disk_speed(None, admin=True), {"source": "files", "n": 1})
            if engine.is_admin():
                self.assertEqual(diagnostics.disk_speed(diagnostics.system_disk(), admin=True)["source"], "disk")

    def test_pings(self):
        results = diagnostics.ping_many(["127.0.0.1"], rounds=3, gap=0.0)
        self.assertEqual(len(results["127.0.0.1"]), 3)
        self.assertTrue(all(isinstance(ms, int) for ms in results["127.0.0.1"]), results)
        with mock.patch.object(diagnostics, "PING_TIMEOUT_MS", 200):
            lost = diagnostics.ping_many(["192.0.2.1"], rounds=2, gap=0.0)  # TEST-NET-1: nobody answers
        self.assertEqual(lost["192.0.2.1"], [None, None])
        with mock.patch.object(diagnostics, "PING_TIMEOUT_MS", 300):
            start = time.perf_counter()
            short = diagnostics.ping_many(["192.0.2.1"], rounds=50, gap=0.0, budget=0.5)
        self.assertLess(time.perf_counter() - start, 5, "the budget stops the rounds")
        self.assertLess(len(short["192.0.2.1"]), 50)
        router = diagnostics.gateway()
        self.assertTrue(router is None or re.fullmatch(r"\d+\.\d+\.\d+\.\d+", router), router)
        found = diagnostics.connection(rounds=1)
        self.assertEqual(set(found), {"gateway", "targets", "dns_ms", "wifi"})
        if found["gateway"]:
            self.assertEqual(found["targets"][found["gateway"]]["sent"], 1)
            self.assertTrue(found["wifi"] is None or 0 <= found["wifi"] <= 100)
        self.assertIsInstance(diagnostics.dns_time(), (int, type(None)))

    def test_mapped_shares_are_knocked_on(self):
        calls = []

        def connect(address, timeout):
            calls.append((address, timeout))
            if address[0] == "nas":
                return mock.MagicMock()  # a context manager that answers
            raise OSError("no route")

        with mock.patch.object(diagnostics, "_subkeys", lambda hive, path: ["z", "y", "x"]), \
                mock.patch.object(diagnostics, "_read", lambda path, name: {
                    r"HKCU\Network\z": r"\\nas\files", r"HKCU\Network\y": r"\\oldpc\share",
                    r"HKCU\Network\x": "not a share"}.get(path)), \
                mock.patch.object(diagnostics.socket, "create_connection", connect):
            found = diagnostics.mapped_shares(timeout=0.2)
        self.assertEqual(found, [{"drive": "Z:", "remote": r"\\nas\files", "alive": True},
                                 {"drive": "Y:", "remote": r"\\oldpc\share", "alive": False}])
        self.assertEqual(calls, [(("nas", 445), 0.2), (("oldpc", 445), 0.2)])
        self.assertIsInstance(diagnostics.mapped_shares(), list)

    def test_full_load_keeps_the_processor_busy(self):
        found = diagnostics.stress(3)
        self.assertEqual((found["seconds"], found["threads"]), (3, os.cpu_count() or 1))
        loads = [t["load"] for t in found["ticks"][1:] if t["load"] is not None]
        self.assertTrue(loads)
        self.assertGreater(max(loads), 40, loads)
        self.assertTrue(all(t["speed"] is None or t["speed"] > 0 for t in found["ticks"]))
        self.assertEqual(len(threading.enumerate()), len([t for t in threading.enumerate() if not t.name.startswith("burn")]),
                         "the burners have finished")

    def test_graphics_adapters_from_directx(self):
        adapters = diagnostics.gpu_adapters()
        for luid, adapter in adapters.items():
            self.assertRegex(luid, r"^0x[0-9A-F]{8}_0x[0-9A-F]{8}$")
            self.assertEqual(set(adapter), {"name", "vram", "software", "discrete"})
            self.assertGreaterEqual(adapter["vram"], 0)
        if adapters:
            self.assertTrue(any(a["software"] for a in adapters.values()), "the Basic Render Driver is always listed")


class LiveGather(unittest.TestCase):
    """gather() runs the live tests after the quick checks and reports every step, without waiting for them here."""

    def setUp(self):
        self.calls = []

        def fake(name, result):
            def run(*args, **kwargs):
                self.calls.append(name)
                return result
            return run

        self.patches = [mock.patch.object(diagnostics, name, fake(name, result)) for name, result in (
            ("watch", watch_facts()), ("stress", stress_facts()), ("connection", connection_facts()),
            ("mapped_shares", []), ("disk_speed", {"sequential": 500.0, "random_ms": 0.2, "random_p95": 0.4,
                                                   "read_mb": 512, "source": "files"}))]
        # A physical PC: on a virtual machine (GitHub's runners are one) the load test is skipped by design
        self.patches.append(mock.patch.object(sysinfo, "model", lambda: "Micro-Star International Co., Ltd. MS-7D76"))
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in self.patches:
            patch.stop()

    def test_every_step_is_reported_in_order(self):
        steps = []
        with mock.patch.multiple(engine, write_value=forbidden, delete_value=forbidden, create_key=forbidden,
                                 delete_key=forbidden, delete_tree=forbidden, set_start_type=forbidden,
                                 run=forbidden, powershell=forbidden):
            facts = diagnostics.gather(steps.append)
        self.assertEqual(steps, diagnostics.STEPS)
        self.assertEqual(sorted(self.calls), ["connection", "disk_speed", "mapped_shares", "stress", "watch"])
        self.assertLess(self.calls.index("watch"), self.calls.index("disk_speed"))
        self.assertLess(self.calls.index("disk_speed"), self.calls.index("stress"))
        for key in ("watch", "stress", "disk_speed", "connection", "shares"):
            self.assertIn(key, facts)
        findings = diagnostics.evaluate(facts)
        self.assertEqual({f.check for f in findings if f.group == "live"} - {"dead_shares"},
                         {c for c, g in diagnostics.CHECKS if g == "live"} - {"dead_shares"})
        render_all(findings)

    def test_a_virtual_machine_skips_the_load_test(self):
        with mock.patch.object(sysinfo, "model", lambda: "VMware, Inc. VMware Virtual Platform"):
            facts = diagnostics.gather()
        self.assertNotIn("stress", self.calls)
        self.assertNotIn("stress", facts)
        self.assertIsNone(diagnostics.check_cpu_throttle(facts))

    def test_a_failing_live_test_leaves_the_others(self):
        def broken(*args, **kwargs):
            raise OSError("no counters")

        with mock.patch.object(diagnostics, "watch", broken):
            steps = []
            facts = diagnostics.gather(steps.append)
        self.assertEqual(steps, diagnostics.STEPS)
        self.assertNotIn("watch", facts)
        self.assertIn("stress", facts)
        findings = {f.check: f for f in diagnostics.evaluate(facts)}
        self.assertEqual(findings["system_pauses"].severity, "unknown")
        self.assertEqual(findings["cpu_throttle"].severity, "ok")


class TweakTraces(unittest.TestCase):
    """What tweaking tools and malware leave behind: blocked programs, policies, removed parts of Windows."""

    def assertFinding(self, finding, severity, line=None, msg=None):
        self.assertIsNotNone(finding, msg)
        self.assertEqual(finding.severity, severity, msg or finding)
        if line:
            self.assertEqual(finding.line, line, msg)
        render_all([finding])

    def test_blocked_programs(self):
        blocked = healthy()["blocked"]
        security = {"program": "securityhealthservice.exe", "debugger": r"C:\WINDOWS\system32\systray.exe",
                    "kind": "protection", "services": ["Windows Security Service"]}
        finding = verdict("blocked_tools", blocked=dict(blocked, programs=[security]))
        self.assertFinding(finding, "warning", "blocked_protection")
        self.assertEqual(finding.items, [("item_blocked_protection", {"name": "securityhealthservice.exe",
                                                                      "debugger": "systray.exe"}),
                                         ("item_blocked_service", {"name": "Windows Security Service"})])
        telemetry = dict(security, program="compattelrunner.exe", kind="windows", services=[])
        self.assertFinding(verdict("blocked_tools", blocked=dict(blocked, programs=[telemetry])), "info",
                           "blocked_windows")
        sign_in = dict(security, program="utilman.exe", debugger="cmd.exe", kind="sign_in", services=[])
        finding = verdict("blocked_tools", blocked=dict(blocked, programs=[telemetry, sign_in]))
        self.assertEqual(finding.items[0][0], "item_blocked_sign_in", "the most dangerous first")
        self.assertFinding(verdict("blocked_tools", blocked=dict(blocked, locks=["taskmgr"])), "warning")
        school = verdict("blocked_tools", blocked=dict(blocked, locks=["taskmgr"]),
                         managed={"domain": True, "entra": False, "mdm": False})
        self.assertFinding(school, "info")
        self.assertIn(("item_managed", {}), school.items)
        self.assertFinding(verdict("blocked_tools", blocked=dict(blocked, firewall=["MsMpEng.exe"])), "warning")
        finding = verdict("blocked_tools", disallowed=["CN=Kaspersky Lab, O=AO Kaspersky Lab, C=RU"])
        self.assertFinding(finding, "warning")
        self.assertEqual(finding.items, [("item_untrusted_vendor", {"name": "Kaspersky Lab"})])
        self.assertFinding(verdict("blocked_tools", disallowed=["CN=DigiNotar Root CA"]), "ok", "blocked_ok")
        self.assertEqual(verdict("blocked_tools", blocked=None).severity, "unknown")

    def test_what_a_debugger_means(self):
        with mock.patch.object(diagnostics, "_windows_program", lambda name: name in ("compattelrunner.exe",)):
            kind = diagnostics.blocked_kind
            self.assertEqual(kind("securityhealthservice.exe", r"C:\WINDOWS\system32\systray.exe"), "protection")
            self.assertEqual(kind("compattelrunner.exe", "%windir%\\System32\\systray.exe"), "windows")
            self.assertEqual(kind("sethc.exe", "cmd.exe"), "sign_in")
            self.assertEqual(kind("chrome.exe", r"C:\ProgramData\upd\host.exe"), "hijack")
            self.assertIsNone(kind("taskmgr.exe", r'"C:\Tools\procexp64.exe"'), "Process Explorer replaces it")
            self.assertIsNone(kind("game.exe", r"C:\Program Files\Microsoft Visual Studio\vsjitdebugger.exe"))
            self.assertIsNone(kind("someapp.exe", "systray.exe"), "a program of its own: the user's choice")
        program = diagnostics.command_program
        self.assertEqual(program('"C:\\Program Files\\App\\app.exe" --x'), "C:\\Program Files\\App\\app.exe")
        self.assertEqual(program("C:\\Program Files\\App\\app.exe --x"), "C:\\Program Files\\App\\app.exe")
        self.assertEqual(program("systray.exe"), "systray.exe")
        self.assertTrue(program("%SystemRoot%\\notepad.exe").lower().endswith("windows\\notepad.exe"))

    def test_security_policies(self):
        security = healthy()["security"]
        self.assertFinding(verdict("security_settings", security=dict(security, smartscreen_off=True)), "warning",
                           "security_off")
        managed = verdict("security_settings", security=dict(security, zone_off=True),
                          managed={"domain": False, "entra": True, "mdm": True})
        self.assertFinding(managed, "info", "security_changed")
        self.assertIn(("item_managed", {}), managed.items)
        policy = dict(security, defender_policies=["DisableRealtimeMonitoring"])
        ignored = verdict("security_settings", security=policy)
        self.assertFinding(ignored, "info", "security_changed")
        self.assertEqual(ignored.items[0][0], "item_defender_policy_ignored", "Tamper Protection keeps it on")
        off = verdict("security_settings", security=policy, defender={"mode": "Normal", "realtime": False,
                                                                       "tamper": False})
        self.assertFinding(off, "warning")
        self.assertEqual(off.items[0][0], "item_defender_policy")
        pending = verdict("security_settings", security=policy, defender={"mode": "Normal", "realtime": True,
                                                                           "tamper": False})
        self.assertEqual(pending.items[0][0], "item_defender_policy_pending")
        self.assertFinding(verdict("security_settings", security=policy,
                                   defender={"mode": "Passive Mode", "realtime": False, "tamper": False}), "ok",
                           msg="another antivirus is at work")
        hidden = verdict("security_settings", security=dict(security, hidden_pages=["windowsdefender"],
                                                            notifications_off=True))
        self.assertFinding(hidden, "info", "security_changed")
        self.assertEqual(hidden.actions, ["security"])

    def test_hidden_settings_pages(self):
        for value, hidden in (("hide:windowsdefender;bluetooth", ["windowsdefender"]),
                              ("showonly:display;windowsupdate", ["windowsdefender"]), ("", []), (None, [])):
            with mock.patch.object(diagnostics, "_read", lambda path, name, v=value: v if "HKLM" in path else None):
                self.assertEqual(diagnostics.hidden_pages(), hidden, value)

    def test_update_blockers(self):
        settings = healthy()["update_settings"]
        local = verdict("windows_update", update_settings=dict(settings, server="http://localhost:8080"))
        self.assertFinding(local, "problem", "wu_server")
        self.assertFinding(verdict("windows_update", update_settings=dict(settings, server="http://wsus:8530")),
                           "warning", "wu_server")
        self.assertFinding(verdict("windows_update", update_settings=dict(settings, server="http://wsus:8530"),
                                   managed={"domain": True, "entra": False, "mdm": False}), "ok",
                           msg="an organization's update server")
        self.assertFinding(verdict("windows_update", update_settings=dict(
            settings, blocked=["DisableWindowsUpdateAccess"])), "warning", "wu_blocked")
        far = NOW + datetime.timedelta(days=400)
        self.assertFinding(verdict("windows_update", update_settings=dict(settings, paused_until=far)), "warning",
                           "wu_paused")
        soon = NOW + datetime.timedelta(days=20)
        self.assertEqual(verdict("windows_update", update_settings=dict(settings, paused_until=soon)).line, "wu_ok")

    def test_update_pause_dates(self):
        values = {"PauseUpdatesExpiryTime": "2027-11-20T09:00:00Z", "PauseQualityUpdatesEndTime": "nonsense"}
        with mock.patch.object(diagnostics, "_read", lambda path, name: values.get(name)):
            self.assertEqual(diagnostics.update_pause().date(), datetime.date(2027, 11, 20))
        with mock.patch.object(diagnostics, "_read", lambda path, name: None):
            self.assertIsNone(diagnostics.update_pause())

    def test_parts_of_windows(self):
        state = healthy()["app_platform"]
        without = [p for p in state["packages"] if not p.startswith("microsoft.windowsstore")]
        finding = verdict("app_platform", app_platform=dict(state, packages=without))
        self.assertFinding(finding, "warning", "platform_missing")
        self.assertEqual(finding.items, [("item_no_store", {})])
        removed = verdict("app_platform", app_platform=dict(state, packages=without,
                                                            deprovisioned=["microsoft.windowsstore_8wekyb3d8bbwe"]))
        self.assertEqual(removed.items, [("item_no_store", {}), ("item_removed_for_all", {})])
        ltsc = dict(healthy()["windows"], edition="EnterpriseS", build=19044)
        no_store = [p for p in without if not p.startswith(("microsoft.desktopappinstaller", "microsoftwindows"))]
        self.assertFinding(verdict("app_platform", app_platform=dict(state, packages=no_store), windows=ltsc), "ok",
                           msg="LTSC has no Store by design")
        windows10 = dict(healthy()["windows"], build=19045)
        no_shell = [p for p in state["packages"] if not p.startswith("microsoftwindows.client.cbs")]
        self.assertEqual(verdict("app_platform", app_platform=dict(state, packages=no_shell), windows=windows10).line,
                         "platform_ok")
        self.assertFinding(verdict("app_platform", app_platform=dict(state, packages=no_shell)), "warning")
        self.assertFinding(verdict("app_platform", app_platform=dict(state, webview2=None)), "warning")
        self.assertFinding(verdict("app_platform", app_platform=dict(state, webview2=None), windows=windows10), "info")
        self.assertFinding(verdict("app_platform", app_platform=dict(state, gaming=True)), "warning")
        self.assertIsNone(verdict("app_platform", windows=dict(healthy()["windows"], server=True)))
        self.assertEqual(verdict("app_platform", app_platform=None).severity, "unknown")

    def test_power_idle_and_sleep(self):
        power = healthy()["power"]
        self.assertFinding(verdict("power_plan", power=dict(power, idle_disable=1)), "warning", "idle_off")
        finding = verdict("power_plan", sleep={"available": False, "causes": ["aoac_override"]})
        self.assertFinding(finding, "info", "sleep_off")
        self.assertEqual(finding.items, [("item_sleep_aoac_override", {})])
        self.assertEqual(verdict("power_plan", sleep={"available": False, "causes": []}).line, "power_ok",
                         "no sleep for a reason of its own: the firmware, a hypervisor")

    def test_network_for_games(self):
        setup = healthy()["network_setup"]
        self.assertFinding(verdict("xbox_network"), "ok", "xbox_ok")
        delay = verdict("xbox_network", network_setup=dict(setup, ipv6=0xFFFFFFFF))
        self.assertFinding(delay, "warning", "xbox_changed")
        self.assertEqual(delay.items, [("item_ipv6_delay", {})])
        gaming = dict(setup, gaming=True)
        self.assertEqual(verdict("xbox_network", network_setup=gaming, teredo=4).items, [("item_teredo_off", {})])
        self.assertEqual(verdict("xbox_network", network_setup=dict(gaming, ipv6=0xFF)).items,
                         [("item_teredo_off", {})])
        merged = verdict("xbox_network", network_setup=dict(gaming, split=0x7FFFFFFF))
        self.assertEqual(merged.items, [("item_svchost_merged", {})])
        self.assertFinding(verdict("xbox_network", network_setup=dict(setup, split=0x7FFFFFFF)), "ok",
                           msg="without Xbox gaming nothing breaks")
        self.assertFinding(verdict("xbox_network", network_setup=dict(setup, ipv6=0xFF)), "info")
        self.assertFinding(verdict("xbox_network", network_setup=dict(setup, ipv6=0x20)), "ok", msg="IPv4 preferred")
        small = dict(healthy()["memory"], total=3 * GB)
        self.assertEqual(verdict("xbox_network", network_setup=gaming, memory=small).line, "xbox_ok",
                         "the default threshold merges services on small PCs by design")

    def test_wmi(self):
        self.assertFinding(verdict("wmi_health"), "ok", "wmi_ok")
        self.assertFinding(verdict("wmi_health", wmi=0x80041010), "warning", "wmi_error")
        self.assertFinding(verdict("wmi_health", wmi_repository=0x80041087), "problem", "wmi_damaged")
        self.assertFinding(verdict("wmi_health", wmi=0, wmi_repository=None), "ok")
        self.assertEqual(verdict("wmi_health", wmi=None, wmi_repository=None).severity, "unknown")


class DrivesAndStarts(unittest.TestCase):
    """What drives report about themselves, how they are connected, and what slows the start down."""

    def assertFinding(self, finding, severity, line=None, msg=None):
        self.assertIsNotNone(finding, msg)
        self.assertEqual(finding.severity, severity, msg or finding)
        if line:
            self.assertEqual(finding.line, line, msg)
        render_all([finding])

    def test_nvme_health(self):
        self.assertFinding(verdict("disk_health"), "ok", "health_ok")
        self.assertEqual(verdict("disk_health").items[0][0], "item_disk_nvme")
        for changes, severity, line in (({"used": 95}, "warning", "ssd_worn"), ({"used": 100}, "problem", "ssd_worn"),
                                        ({"critical": 0x04}, "problem", "nvme_critical"),
                                        ({"critical": 0x02, "temperature": 84}, "warning", "nvme_hot"),
                                        ({"spare": 5}, "problem", "nvme_spare"),
                                        ({"spare": 10}, "warning", "nvme_spare"),
                                        ({"media_errors": 3}, "warning", "nvme_media_errors"),
                                        ({"spare": 0, "spare_threshold": 0}, "ok", "health_ok")):
            self.assertFinding(verdict("disk_health", drive_health={"0": nvme(**changes)}), severity, line)
        # Windows' own counter still counts where the drive's report could not be read
        self.assertFinding(verdict("disk_health", drive_health={}, wear=[{"id": "0", "wear": 95}]), "warning",
                           "ssd_worn")

    def test_hard_disk_sectors(self):
        disk = {"id": "1", "name": "WDC WD20EZAZ", "media": "HDD", "health": "Healthy", "bus": "SATA"}
        report = {"kind": "ata", "reallocated": 8, "pending": 1, "uncorrectable": 0, "hours": 21000}
        finding = verdict("disk_health", disks=healthy()["disks"] + [disk], drive_health={"1": report})
        self.assertFinding(finding, "warning", "hdd_sectors")
        self.assertEqual(finding.params["reallocated"], 8)
        clean = dict(report, reallocated=0, pending=0)
        self.assertEqual(verdict("disk_health", disks=[disk], drive_health={"1": clean}).line, "health_ok")

    def test_parse_nvme_log(self):
        log = bytearray(512)
        log[0], log[1:3], log[3], log[4], log[5] = 0, (273 + 45).to_bytes(2, "little"), 97, 10, 12
        log[48:64] = (200_000_000).to_bytes(16, "little")
        log[128:144], log[144:160], log[160:176] = (5000).to_bytes(16, "little"), (40).to_bytes(16, "little"), \
            (2).to_bytes(16, "little")
        parsed = diagnostics.parse_nvme_health(bytes(log))
        self.assertEqual((parsed["temperature"], parsed["spare"], parsed["used"], parsed["hours"], parsed["unsafe"],
                          parsed["media_errors"]), (45, 97, 12, 5000, 40, 2))
        self.assertEqual(parsed["written"], 200_000_000 * 512_000)
        self.assertIsNone(diagnostics.parse_nvme_health(bytes(512)), "an empty page")

    def test_parse_ata_smart(self):
        data = bytearray(512)
        for slot, (attribute, raw) in enumerate(((0x05, 16), (0x09, 21_000), (0xC5, 2), (0xC6, 0))):
            entry = 2 + slot * 12
            data[entry] = attribute
            data[entry + 5:entry + 11] = raw.to_bytes(6, "little")
        parsed = diagnostics.parse_ata_smart(bytes(data))
        self.assertEqual(parsed, {"kind": "ata", "reallocated": 16, "pending": 2, "uncorrectable": 0, "hours": 21000})
        self.assertIsNone(diagnostics.parse_ata_smart(bytes(512)))

    def test_drive_link(self):
        self.assertFinding(verdict("drive_link"), "ok", "drive_link_ok")
        slower = verdict("drive_link", drive_links={"0": (3, 4, 4, 4)})
        self.assertFinding(slower, "info", "drive_link_slow")
        self.assertEqual(slower.params["max_speed"], 4)
        self.assertFinding(verdict("drive_link", drive_links={"0": (4, 2, 4, 4)}), "warning")
        self.assertIsNone(verdict("drive_link", drive_links={}))
        # Without administrator rights the generation is not judged, and not shown as the best one either
        lanes = verdict("drive_link", drive_links={"0": (None, 4, 4, 4)})
        self.assertFinding(lanes, "ok", "drive_link_lanes_ok")
        self.assertEqual(lanes.items[0][0], "item_link_lanes")
        self.assertFinding(verdict("drive_link", drive_links={"0": (None, 2, 4, 4)}), "warning", "drive_link_narrow")
        both = verdict("drive_link", drive_links={"0": (4, 2, 4, 4), "1": (3, 4, 4, 4)})
        self.assertEqual((both.severity, both.params["name"]), ("warning", "Samsung SSD 980"), "the worse first")
        self.assertEqual(diagnostics.disk_instance(
            "\\\\?\\scsi#disk&ven_nvme&prod_wd_black_sn850x#5&18a29b35&0&000000#{53f56307-b6bf-11d0-94f2-00a0c91efb8b}"),
            "SCSI\\DISK&VEN_NVME&PROD_WD_BLACK_SN850X\\5&18A29B35&0&000000")
        self.assertIsNone(diagnostics.disk_instance(""))

    def test_file_system(self):
        self.assertFinding(verdict("volume_health"), "ok", "volumes_ok")
        for health, severity in ((1, "info"), (2, "warning"), (3, "problem")):
            self.assertFinding(verdict("volume_health", volumes=[{"drive": "C", "health": health}]), severity,
                               "volumes_damaged")
        dirty = verdict("volume_health", dirty=["C:"])
        self.assertFinding(dirty, "warning")
        self.assertEqual(dirty.items, [("item_volume_dirty", {"drive": "C:"})])
        self.assertEqual(verdict("volume_health", volumes=None, admin=False).line, "unknown_admin")

    def test_startup_time(self):
        finding = verdict("boot_time")
        self.assertFinding(finding, "ok", "boot_time_ok")
        self.assertEqual(finding.params["seconds"], 30)
        driver = [culprit(102, "FACEIT", 1850, days_ago=d) for d in (1, 3, 6)]
        slowed = verdict("boot_time", perf_events=healthy()["perf_events"] + driver)
        self.assertFinding(slowed, "info", "boot_slowed")
        self.assertEqual(slowed.items, [("item_slow_driver", {"name": "FACEIT", "seconds": 1.9, "n": 3})])
        self.assertEqual(slowed.actions, ["devices"])
        once = verdict("boot_time", perf_events=healthy()["perf_events"] + driver[:1])
        self.assertEqual(once.line, "boot_time_ok", "once can be a one-off")
        heavy = [culprit(103, "Slow Service", 4000, days_ago=d) for d in (1, 3)] + \
            [culprit(203, "Backup Service", 2500, days_ago=d) for d in (1, 3)]
        self.assertFinding(verdict("boot_time", perf_events=healthy()["perf_events"] + heavy), "warning")
        apps = [culprit(101, "pycharm64.exe", 90_000, days_ago=d) for d in (1, 3, 6)]
        self.assertEqual(verdict("boot_time", perf_events=healthy()["perf_events"] + apps).line, "boot_time_ok",
                         "programs opened right after sign-in do not count")
        updates = [boot(days_ago=1, total=200_000, after_install=True), boot(days_ago=2)]
        self.assertEqual(verdict("boot_time", perf_events=updates).params["seconds"], 30)
        self.assertEqual(verdict("boot_time", perf_events=None, admin=False).line, "unknown_admin")
        dps = [("DPS", "Diagnostic Policy Service", "diagnostics")]
        self.assertEqual(verdict("boot_time", perf_events=[], disabled_services=dps).line, "unknown_dps")
        self.assertIsNone(verdict("boot_time", perf_events=[]))

    def test_video_memory(self):
        def short(days_ago, scenario="2"):
            return {"id": 500, "time": NOW - datetime.timedelta(days=days_ago),
                    "data": {"Scenario": scenario, "DisplayDeviceFriendlyName": CARD, "MemorySize": "3842306048"}}

        finding = verdict("video_memory", perf_events=[short(d) for d in (1, 2, 3)])
        self.assertFinding(finding, "info", "vram_short")
        self.assertEqual((finding.params["n"], finding.params["name"]), (3, CARD))
        self.assertIsNone(verdict("video_memory", perf_events=[short(d) for d in (1, 2)]))
        self.assertIsNone(verdict("video_memory", perf_events=[short(d, "1") for d in (1, 2, 3)]))
        self.assertIsNone(verdict("video_memory", perf_events=[short(d) for d in (40, 41, 42)]), "too long ago")

    def test_interrupts(self):
        cpu = healthy()["cpu"]
        self.assertFinding(verdict("cpu_load", cpu=dict(cpu, interrupts=7.5)), "warning", "interrupts_high")
        self.assertFinding(verdict("cpu_load", cpu=dict(cpu, interrupts_now=31.0)), "warning", "interrupts_high")
        busy = verdict("cpu_load", cpu=dict(cpu, load=85.0, interrupts=7.5))
        self.assertEqual((busy.line, busy.items[0][0]), ("cpu_high", "item_interrupts"))
        self.assertEqual(verdict("cpu_load", cpu={"load": 10.0, "top": []}).line, "cpu_ok", "older facts")
        before = [(1000, 10), (1000, 50)]
        after = [(2000, 20), (2000, 350)]
        self.assertEqual(diagnostics.interrupt_share(before), 5.0)
        self.assertEqual(diagnostics.interrupt_share(before, after), 30.0)
        self.assertIsNone(diagnostics.interrupt_share(None))

    def test_startup_impact(self):
        heavy = {"name": "Proton Mail Bridge", "cpu": 3015, "disk": 206_734_848, "starts": 5}
        finding = verdict("startup_apps", startup_impact=[heavy] + healthy()["startup_impact"])
        self.assertFinding(finding, "info", "startup_heavy")
        self.assertEqual(finding.items[0], ("item_startup_heavy", {"name": "Proton Mail Bridge", "seconds": 3.0,
                                                                  "size": 206_734_848}))
        many = verdict("startup_apps", startup=[f"App {i}" for i in range(12)], startup_impact=[heavy])
        self.assertEqual((many.severity, many.line), ("warning", "startup_many"))

    def test_startup_entries_that_start_nothing(self):
        finding = verdict("startup_apps", startup_dead=["Old Tool"])
        self.assertFinding(finding, "info", "startup_dead")
        self.assertEqual(finding.items[0], ("item_startup_dead", {"name": "Old Tool"}))
        self.assertEqual(finding.actions, ["startup"], "the Startup page removes them")

    def test_startup_trees(self):
        data = ('<?xml version="1.0" encoding="UTF-16"?><StartupData>'
                '<Process Name="C:\\Apps\\bridge-launcher.exe" PID="10"><CpuUsage>1000000</CpuUsage>'
                '<DiskUsage>5000</DiskUsage><ParentPID>4</ParentPID></Process>'
                '<Process Name="C:\\Apps\\bridge.exe" PID="11"><CpuUsage>2000000</CpuUsage>'
                '<DiskUsage>7000</DiskUsage><ParentPID>10</ParentPID></Process>'
                '<Process Name="C:\\Other\\tool.exe" PID="20"><CpuUsage>5000</CpuUsage>'
                '<DiskUsage>0</DiskUsage><ParentPID>4</ParentPID></Process>'
                '</StartupData>').encode("utf-16")
        self.assertEqual(sorted(diagnostics.startup_trees(data)),
                         [("C:\\Apps\\bridge-launcher.exe", 3_000_000, 12_000), ("C:\\Other\\tool.exe", 5000, 0)])

    def test_stop_codes(self):
        self.assertEqual(diagnostics.stop_cause("0x00000116"), "graphics")
        self.assertEqual(diagnostics.stop_cause("0x0000000A"), "driver")
        self.assertEqual(diagnostics.stop_cause("0x00000124"), "hardware")
        self.assertIsNone(diagnostics.stop_cause("0x00001234"))
        self.assertIsNone(diagnostics.stop_cause("?"))
        finding = verdict("crashes", events=[event("Microsoft-Windows-Kernel-Power", 41, args=["278", "0"])])
        self.assertEqual(finding.items[0][0], "item_bsod_cause")
        self.assertEqual(finding.items[0][1]["code"], "0x00000116")
        render_all([finding])

    def test_battery_cycles(self):
        laptop = dict(healthy()["power"], battery=True)
        finding = verdict("battery", power=laptop, battery={"design": 50_000, "full": 45_000}, battery_cycles=312)
        self.assertEqual(finding.items, [("item_battery_cycles", {"n": 312})])
        render_all([finding])


class ProtectionAndRecovery(unittest.TestCase):
    """Defender, browser policies, trusted roots, accounts, network exposure, encryption, recovery and the clock."""

    def assertFinding(self, finding, severity, line=None, msg=None):
        self.assertIsNotNone(finding, msg)
        self.assertEqual(finding.severity, severity, msg or finding)
        if line:
            self.assertEqual(finding.line, line, msg)
        render_all([finding])

    def test_recovery_environment(self):
        self.assertFinding(verdict("recovery_env"), "ok", "recovery_ok")
        self.assertFinding(verdict("recovery_env", recovery={"enabled": False}), "warning", "recovery_off")
        self.assertEqual(verdict("recovery_env", recovery=None).severity, "unknown")
        self.assertIsNone(verdict("recovery_env", windows=dict(healthy()["windows"], server=True)))
        with tempfile.TemporaryDirectory() as root:
            folder = os.path.join(root, "System32", "Recovery")
            os.makedirs(folder)
            with open(os.path.join(folder, "ReAgent.xml"), "w", encoding="utf-8") as f:
                f.write("<?xml version='1.0' encoding='utf-8'?><WindowsRE version=\"2.0\">"
                        "<InstallState state=\"0\"/></WindowsRE>")
            with mock.patch.dict(os.environ, {"SystemRoot": root}):
                self.assertEqual(diagnostics.recovery_environment(), {"enabled": False})
            with mock.patch.dict(os.environ, {"SystemRoot": os.path.join(root, "missing")}):
                self.assertIsNone(diagnostics.recovery_environment())

    def test_clock(self):
        time_service = "Microsoft-Windows-Time-Service"
        self.assertFinding(verdict("time_sync"), "ok", "time_ok")
        stuck = verdict("time_sync", time_events=[event(time_service, 37, days_ago=6, level=4),
                                                  event(time_service, 36, days_ago=2, level=3)])
        self.assertFinding(stuck, "warning", "time_stuck")
        self.assertEqual(verdict("time_sync", time_events=[event(time_service, 36, days_ago=3, level=3),
                                                           event(time_service, 37, days_ago=1, level=4)]).line,
                         "time_ok", "synchronised again since")
        self.assertFinding(verdict("time_sync", time_events=[]), "ok", "time_quiet")
        self.assertEqual(verdict("time_sync", time_events=None).severity, "unknown")

    def test_defender(self):
        self.assertFinding(verdict("defender"), "ok", "defender_ok")
        severe = verdict("defender", threats=[{"name": "Trojan:Win32/Wacatac.B!ml", "severity": 5}])
        self.assertFinding(severe, "problem", "defender_threats")
        self.assertFinding(verdict("defender", threats=[{"name": "PUA:Win32/Presenoker", "severity": 2}]), "warning")
        hosts = verdict("defender", threats=[{"name": "SettingsModifier:Win32/PossibleHostsFileHijack",
                                              "severity": 2}])
        self.assertFinding(hosts, "info", "defender_notes")
        broad = verdict("defender", defender_exclusions={"paths": ["C:\\", "D:\\Games"], "extensions": [],  # made-up test data, secret-scan: allow
                                                         "processes": []})
        self.assertFinding(broad, "warning", "defender_weakened")
        self.assertEqual(broad.items, [("item_exclusion_broad", {"name": "C:\\"}), ("item_exclusions", {"n": 2})])
        self.assertFinding(verdict("defender", defender_exclusions={"paths": ["D:\\Games"], "extensions": [],  # made-up test data, secret-scan: allow
                                                                    "processes": []}), "info", "defender_notes")
        self.assertFinding(verdict("defender", defender={"mode": "Normal", "realtime": True, "tamper": False}),
                           "warning", "defender_weakened")
        self.assertFinding(verdict("defender", defender={"mode": "Normal", "realtime": True, "tamper": False},
                                   managed={"domain": True, "entra": False, "mdm": False}), "ok",
                           msg="an organization manages Tamper Protection")
        self.assertIsNone(verdict("defender", defender={"mode": "Passive Mode", "realtime": False, "tamper": False}),
                          "another antivirus is at work")
        self.assertEqual(verdict("defender", defender_exclusions=None, threats=None, admin=False).line,
                         "unknown_admin")
        # Without administrator rights only the threats can be read: no claim about the exclusions
        self.assertEqual(verdict("defender", defender_exclusions=None, admin=False).line, "unknown_admin")
        partial = verdict("defender", defender_exclusions=None, admin=False,
                          threats=[{"name": "SettingsModifier:Win32/PossibleHostsFileHijack", "severity": 2}])
        self.assertFinding(partial, "info", "defender_notes")
        self.assertEqual(partial.items[-1], ("item_exclusions_unknown", {}))

    def test_broad_exclusions(self):
        broad = diagnostics.broad_exclusion
        for kind, value in (("paths", "C:\\"), ("paths", "c:"), ("paths", "%TEMP%"), ("paths", "*"),
                            ("paths", os.path.expandvars("%USERPROFILE%\\Downloads")), ("extensions", ".exe"),
                            ("extensions", "PS1"), ("processes", r"C:\Windows\System32\WindowsPowerShell\v1.0"
                                                                 r"\powershell.exe")):
            self.assertTrue(broad(kind, value), (kind, value))
        for kind, value in (("paths", r"D:\Games\Steam"), ("paths", os.path.expandvars("%TEMP%\\build")),  # made-up test data, secret-scan: allow
                            ("extensions", "log"), ("processes", "game.exe")):
            self.assertFalse(broad(kind, value), (kind, value))

    def test_browser_policies(self):
        forced = [{"browser": "Google Chrome", "kind": "extensions", "value": "abcdefghijklmnopabcdefghijklmnop"},
                  {"browser": "Microsoft Edge", "kind": "search", "value": "https://search.example/?q={searchTerms}"}]
        finding = verdict("browser_policies", browser_policies=forced)
        self.assertFinding(finding, "warning", "browser_forced")
        self.assertEqual([key for key, _ in finding.items], ["item_policy_extensions", "item_policy_search"])
        work = verdict("browser_policies", browser_policies=forced, managed={"domain": True, "entra": False,
                                                                            "mdm": False})
        self.assertFinding(work, "info")
        self.assertIn(("item_managed", {}), work.items)
        self.assertFinding(verdict("browser_policies"), "ok", "browser_ok")
        self.assertEqual(verdict("browser_policies", browser_policies=None).severity, "unknown")

    def test_browser_policy_facts(self):
        chrome, edge = diagnostics.BROWSER_POLICY_KEYS[0][1], diagnostics.BROWSER_POLICY_KEYS[1][1]
        values = {
            (winreg.HKEY_LOCAL_MACHINE, chrome + r"\ExtensionInstallForcelist"):
                [("1", "abcdefghijklmnopabcdefghijklmnop;https://clients2.google.com/service/update2/crx")],
            (winreg.HKEY_LOCAL_MACHINE, chrome): [("ExtensionSettings", '{"ponmlkjihgfedcbaponmlkjihgfedcba": '
                                                                        '{"installation_mode": "force_installed"}}')],
            (winreg.HKEY_CURRENT_USER, edge): [("HomepageLocation", "https://start.example"),
                                               ("DefaultSearchProviderEnabled", 0),
                                               ("DefaultSearchProviderSearchURL", "https://ignored.example")],
        }
        with mock.patch.object(diagnostics, "_values", lambda hive, path: values.get((hive, path), [])), \
                mock.patch.object(diagnostics, "firefox_policies", lambda: []):
            found = diagnostics.browser_policies()
        self.assertEqual(found, [
            {"browser": "Google Chrome", "kind": "extensions",
             "value": "abcdefghijklmnopabcdefghijklmnop, ponmlkjihgfedcbaponmlkjihgfedcba"},
            {"browser": "Microsoft Edge", "kind": "homepage", "value": "https://start.example"}])

    def test_root_certificates(self):
        self.assertFinding(verdict("root_certificates"), "ok", "roots_ok")
        added = verdict("root_certificates", added_roots=[{"name": "Example Ad Injector Root", "user": True}])
        self.assertFinding(added, "info", "roots_added")
        self.assertEqual(added.items, [("item_root_user", {"name": "Example Ad Injector Root"})])
        self.assertEqual(verdict("root_certificates", added_roots=None).severity, "unknown")
        self.assertIsNone(diagnostics.certificate_name(bytes(8)), "no certificate in the blob")

    def test_accounts(self):
        users = healthy()["local_users"]
        guest = [dict(u, enabled=True) if u["sid"].endswith("-501") else u for u in users]
        finding = verdict("accounts", local_users=guest)
        self.assertFinding(finding, "warning", "accounts_risky")
        self.assertEqual(finding.items, [("item_guest_on", {"name": "Guest"})])
        admin = [dict(u, enabled=True) if u["sid"].endswith("-500") else u for u in users]
        self.assertFinding(verdict("accounts", local_users=admin), "warning")
        self.assertFinding(verdict("accounts", local_users=admin, managed={"domain": True, "entra": False,
                                                                          "mdm": False}), "info")
        hidden = verdict("accounts", account_settings={"hidden": ["Player", "Old"], "autologon_password": False})
        self.assertEqual(hidden.items, [("item_account_hidden", {"name": "Player"})], "only an account in use")
        self.assertFinding(verdict("accounts", account_settings={"hidden": [], "autologon_password": True}),
                           "warning")
        self.assertEqual(verdict("accounts", local_users=None, account_settings=None).severity, "unknown")

    def test_network_exposure(self):
        self.assertFinding(verdict("network_exposure"), "ok", "exposure_ok")
        public = dict(healthy()["firewall"], public=False)
        self.assertFinding(verdict("network_exposure", firewall=public), "problem", "exposure_open")
        self.assertFinding(verdict("network_exposure", firewall=dict(healthy()["firewall"], private=False)),
                           "warning")
        self.assertFinding(verdict("network_exposure", firewall=public, firewall_products=["ESET Firewall"]), "ok",
                           msg="another firewall does the job")
        self.assertFinding(verdict("network_exposure", firewall=dict(healthy()["firewall"], domain=False)), "ok",
                           msg="the domain profile of a PC outside a domain")
        self.assertFinding(verdict("network_exposure", smb1=["SMB1Protocol", "SMB1Protocol-Server"]), "warning")
        self.assertFinding(verdict("network_exposure", smb1=["SMB1Protocol-Client"]), "info")
        desktop = healthy()["remote_desktop"]
        self.assertFinding(verdict("network_exposure", remote_desktop=dict(desktop, on=True)), "info")
        self.assertFinding(verdict("network_exposure", remote_desktop=dict(desktop, on=True, nla_off=True)),
                           "warning")
        self.assertFinding(verdict("network_exposure", remote_desktop=dict(desktop, wrapper=True)), "info")
        self.assertEqual(verdict("network_exposure", firewall=None, remote_desktop=None).severity, "unknown")

    def test_remote_tools(self):
        programs = {"anydesk": ("AnyDesk", "9.5"), "parsec": ("Parsec", "150"),
                    "teamviewer": ("TeamViewer", "15.60")}
        finding = verdict("remote_tools", software=dict(healthy()["software"], programs=programs))
        self.assertFinding(finding, "info", "remote_installed")
        self.assertEqual(finding.params["names"], "AnyDesk, TeamViewer")
        self.assertIsNone(verdict("remote_tools", software=dict(healthy()["software"],
                                                                programs={"parsec": ("Parsec", "150")})))

    def test_drive_encryption(self):
        self.assertFinding(verdict("bitlocker"), "ok", "bitlocker_off")
        protected = {"conversion": 1, "protection": 1, "recovery": ["{1a2b3c4d-1111-2222-3333-444455556666}"]}
        finding = verdict("bitlocker", bitlocker=protected)
        self.assertFinding(finding, "info", "bitlocker_key")
        self.assertEqual(finding.params["id"], "1A2B3C4D")
        self.assertFinding(verdict("bitlocker", bitlocker=dict(protected, protection=0)), "info",
                           "bitlocker_suspended")
        self.assertFinding(verdict("bitlocker", bitlocker=dict(protected, recovery=[])), "warning",
                           "bitlocker_no_key")
        self.assertEqual(verdict("bitlocker", bitlocker=None, admin=False).line, "unknown_admin")

    def test_secure_boot_certificates(self):
        firmware = healthy()["firmware"]
        pending = verdict("secure_boot", firmware=dict(firmware, ca2023="InProgress"))
        self.assertFinding(pending, "info", "secure_ca")
        self.assertEqual(pending.items, [("item_ca2023_pending", {})])
        failed = verdict("secure_boot", firmware=dict(firmware, ca2023="NotStarted", ca2023_error=0x80070057))
        self.assertFinding(failed, "warning", "secure_ca")
        self.assertEqual(failed.items, [("item_ca2023_failed", {"code": "0x80070057"})])
        off = verdict("secure_boot", firmware=dict(firmware, secure_boot=False, ca2023="NotStarted"))
        self.assertEqual(off.items, [("item_secure_boot_off", {})], "with Secure Boot off the certificates wait")

    def test_driver_blocklist(self):
        security = dict(healthy()["security"], blocklist_off=True)
        finding = verdict("security_settings", security=security)
        self.assertFinding(finding, "warning", "security_off")
        self.assertEqual(finding.items[0][0], "item_blocklist_off")
        hvci = dict(healthy()["boot"], integrity=diagnostics.CI_ENABLED | diagnostics.CI_HVCI)
        self.assertFinding(verdict("security_settings", security=security, boot=hvci), "ok",
                           msg="memory integrity enforces the list anyway")
        self.assertFinding(verdict("security_settings", security=security,
                                   windows=dict(healthy()["windows"], build=19045)), "ok",
                           msg="Windows 10 had it off by default")


class Facts(unittest.TestCase):
    def test_hosts_file(self):
        with tempfile.TemporaryDirectory() as folder:
            # Not named "hosts": an antivirus watches files of that name for blocked Microsoft addresses
            path = os.path.join(folder, "hosts-copy.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("# comment 0.0.0.0 update.microsoft.com\n127.0.0.1 localhost\n::1 localhost\n"
                        "0.0.0.0 vortex.data.microsoft.com settings-win.data.microsoft.com\n"
                        "0.0.0.0 fe2.update.microsoft.com  # breaks Windows Update\n"
                        "10.0.0.5 myserver\n")
            with mock.patch.object(diagnostics, "hosts_path", lambda: path):
                self.assertEqual(diagnostics.hosts(), {"entries": 4, "blocked": ["fe2.update.microsoft.com"]})
        with mock.patch.object(diagnostics, "hosts_path", lambda: os.path.join(folder, "missing")):
            self.assertEqual(diagnostics.hosts(), {"entries": 0, "blocked": []})

    def test_startup_programs(self):
        hkcu, hklm = winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE
        approved = diagnostics.APPROVED
        values = {
            (hkcu, diagnostics.RUN_KEYS[0][1]): [("Discord", "discord.exe"), ("Old", "old.exe")],
            (hkcu, approved + r"\Run"): [("Old", b"\x03\x00"), ("Discord", b"\x02\x00")],
            (hklm, diagnostics.RUN_KEYS[1][1]): [("SecurityHealth", "x.exe"), ("Driver tool", "y.exe")],
            (hklm, approved + r"\Run"): [("SecurityHealth", b"\x07\x00")],
            (hkcu, diagnostics.APP_TASKS + r"\Vendor.Chat_123\Start"): [("State", 2)],
            (hkcu, diagnostics.APP_TASKS + r"\Vendor.Off_456\Start"): [("State", 1)],
            (hkcu, approved + r"\StartupFolder"): [("Tool.lnk", b"\x03")],
        }
        subkeys = {(hkcu, diagnostics.APP_TASKS): ["Vendor.Chat_123", "Vendor.Off_456"],
                   (hkcu, diagnostics.APP_TASKS + r"\Vendor.Chat_123"): ["Start"],
                   (hkcu, diagnostics.APP_TASKS + r"\Vendor.Off_456"): ["Start"]}

        def listdir(folder):
            if folder.lower().endswith(r"programs\startup") and "appdata" in folder.lower():
                return ["desktop.ini", "Tool.lnk", "Notes.lnk"]
            raise FileNotFoundError(folder)

        with mock.patch.object(diagnostics, "_values", lambda hive, path: values.get((hive, path), [])), \
                mock.patch.object(diagnostics, "_subkeys", lambda hive, path: subkeys.get((hive, path), [])), \
                mock.patch.object(diagnostics.os, "listdir", listdir):
            self.assertEqual(diagnostics.startup_programs(), ["Discord", "Driver tool", "Notes", "Chat"])

    def test_page_file_lines(self):
        self.assertEqual(diagnostics.page_file_entry("C:\\pagefile.sys 1024 4096"), ("C:", 1024, 4096))
        self.assertEqual(diagnostics.page_file_entry("?:\\pagefile.sys"), ("?:", 0, 0))
        self.assertEqual(diagnostics.page_file_entry("d:\\pagefile.sys 0 0"), ("D:", 0, 0))

    def test_powershell_answers(self):
        class Process:
            def __init__(self, out):
                self.out = out

            def communicate(self, timeout=None):
                return self.out, b""

        answer = {"disks": {"id": "0", "name": "SSD", "media": "SSD", "health": "Healthy", "bus": "NVMe"},
                  "devices": None, "antivirus": [{"name": "Defender", "state": 397568}],
                  "last_update": "2026-10-20T10:00:00", "image": "Healthy", "cpu_hardware_threads": 20,
                  "events": {"id": 41, "provider": "Microsoft-Windows-Kernel-Power", "level": 1,
                             "time": "2026-10-05T12:19:48", "args": "0"},
                  "nvidia_events": [], "app_events": [], "battery": {"design": 50000, "full": [20000, 5000]}}
        facts = diagnostics.finish_powershell(Process(("\ufeff" + json.dumps(answer)).encode("utf-8")))
        self.assertEqual(facts["disks"][0]["name"], "SSD", "a list of one comes as the item itself")
        self.assertEqual(facts["devices"], [], "an empty list comes as null")
        self.assertEqual(facts["events"][0]["args"], ["0"])
        self.assertEqual(facts["events"][0]["time"], datetime.datetime(2026, 10, 5, 12, 19, 48))
        self.assertEqual(facts["last_update"], datetime.datetime(2026, 10, 20, 10))
        self.assertEqual(facts["battery"], {"design": 50000, "full": 25000})
        self.assertEqual((facts["image"], facts["cpu_hardware_threads"], facts["nvidia_events"]), ("Healthy", 20, []))
        self.assertNotIn("whea", facts, "a part that failed stays missing")
        self.assertEqual(diagnostics.finish_powershell(Process(b"not json")), {})

    def test_the_script_only_reads(self):
        # The cmdlets with a changing verb only read: the health Windows has already recorded, and the list of a
        # volume's BitLocker key protectors
        script = diagnostics.POWERSHELL_SCRIPT.replace("Repair-WindowsImage -Online -CheckHealth", "")
        self.assertEqual(script.count("Invoke-CimMethod"), script.count("-MethodName GetKeyProtectors"))
        script = script.replace("Invoke-CimMethod", "")
        cmdlets = set(re.findall(r"\b([A-Z][a-z]+)-([A-Z][A-Za-z]+)\b", script))
        changing = {"Set", "Remove", "Stop", "Start", "Restart", "Invoke", "Enable", "Disable", "Clear", "Add",
                    "Register", "Unregister", "Install", "Uninstall", "Update", "Rename", "Move", "Copy", "Out",
                    "Export", "Import", "Mount", "Dismount", "Suspend", "Resume", "Reset", "Repair", "Optimize",
                    "Initialize", "Format", "Grant", "Revoke", "Block", "Unblock", "Save", "Send", "Write", "Edit",
                    "Sync"}
        self.assertEqual({verb for verb, _ in cmdlets} & changing, set())
        self.assertEqual({noun for verb, noun in cmdlets if verb == "New"}, {"Object"})
        # COM objects only read: the last update's date, and whether the firewall is on (FirewallEnabled)
        self.assertEqual(re.findall(r"New-Object\s+(?:-ComObject\s+)?([\w.]+)", diagnostics.POWERSHELL_SCRIPT),
                         ["Text.UTF8Encoding", "Microsoft.Update.AutoUpdate", "HNetCfg.FwPolicy2"])
        self.assertNotRegex(diagnostics.POWERSHELL_SCRIPT, r"\$fw\.\w+\s*=", "the firewall is never set")
        # The script is passed as the command line itself: quotes or backslashes would need escaping
        self.assertNotIn('"', diagnostics.POWERSHELL_SCRIPT)
        self.assertNotIn("\\", diagnostics.POWERSHELL_SCRIPT)


def forbidden(*args, **kwargs):
    raise AssertionError("troubleshooting must never change the system")


class ThisPc(unittest.TestCase):
    def test_a_real_check_reads_only(self):
        steps = []
        with mock.patch.multiple(engine, write_value=forbidden, delete_value=forbidden, create_key=forbidden,
                                 delete_key=forbidden, delete_tree=forbidden, set_start_type=forbidden,
                                 run=forbidden, powershell=forbidden):
            facts = diagnostics.gather(steps.append, live=False)
        self.assertEqual(steps, diagnostics.STEPS[:4])
        for key in ("memory", "cpu", "drives", "uptime", "startup", "hosts", "windows", "pool", "boot", "power",
                    "processor", "security", "firmware", "vc_runtime"):
            self.assertIn(key, facts)
        findings = diagnostics.evaluate(facts)
        self.assertGreater(len(findings), 30)
        render_all(findings)

    def test_the_live_tests_run_on_this_pc(self):
        """The watch, the load, the drive and the connection with the shortest durations: the readings are real."""
        with mock.patch.multiple(engine, write_value=forbidden, delete_value=forbidden, create_key=forbidden,
                                 delete_key=forbidden, delete_tree=forbidden, set_start_type=forbidden,
                                 run=forbidden, powershell=forbidden):
            watch = diagnostics.watch(2)
            stress = diagnostics.stress(2, threads=2)
            speed = diagnostics.disk_speed(diagnostics.system_disk(), engine.is_admin())
            connection = diagnostics.connection(rounds=2)
            shares = diagnostics.mapped_shares()
        self.assertEqual(watch["seconds"], 2)
        for key in ("cpu", "cpu_time", "speed", "free_mb", "commit", "disks", "gpu", "pause_ms", "hung", "top_cpu"):
            self.assertIn(key, watch["ticks"][0])
        self.assertTrue(watch["ticks"][1]["disks"], "every PC has a drive with counters")
        self.assertGreater(watch["ram_mb"], 1000)
        self.assertEqual(watch["missing"], [])
        self.assertEqual(stress["seconds"], 2)
        self.assertIsNotNone(stress["ticks"][1]["speed"])
        if speed is not None:
            self.assertGreater(speed["sequential"], 0)
            self.assertIn(speed["source"], ("disk", "files"))
        self.assertIn("gateway", connection)
        if connection["gateway"]:
            self.assertEqual(set(connection["targets"]), {connection["gateway"], *diagnostics.INTERNET_HOSTS})
            self.assertEqual(connection["targets"][connection["gateway"]]["sent"], 2)
        self.assertIsInstance(shares, list)
        self.assertIsNotNone(diagnostics.wait_chain(threading.main_thread().native_id))
        self.assertNotIn(os.getpid(), [pid for pid, _, _ in diagnostics.hung_windows()])
        facts = dict(healthy(), watch=watch, stress=stress, disk_speed=speed, connection=connection, shares=shares)
        render_all([f for f in diagnostics.evaluate(facts) if f.group == "live"])


class Texts(unittest.TestCase):
    def test_every_check_is_explained(self):
        for lang, texts in i18n.TEXTS.items():
            for check, group in diagnostics.CHECKS:
                title, details = texts["diag"][check]
                self.assertTrue(title, (lang, check))
                self.assertGreater(len(details), 150, (lang, check))
            for step in diagnostics.STEPS:
                self.assertIn("diag_step_" + step, texts["ui"])
            for action in diagnostics.ACTIONS:
                self.assertIn("act_" + action, texts["ui"])
            for severity in diagnostics.SEVERITIES:
                self.assertIn("diag_" + severity, texts["ui"])
            for _, effect in diagnostics.CORE_SERVICES + diagnostics.OPTIONAL_SERVICES + [("", "compression")]:
                self.assertIn("effect_" + effect, texts["diag_lines"])

    def test_actions_open_something_real(self):
        for action in diagnostics.ACTIONS:
            kind, target, args = diagnostics.action_target(action)
            self.assertIn(kind, ("page", "open"))
            self.assertNotIn("%", target + (args or ""), action)


if __name__ == "__main__":
    unittest.main()

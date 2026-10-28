"""Troubleshooting: every verdict on made-up facts, the texts of every finding, and a read-only run on this PC."""
import datetime
import json
import os
import re
import tempfile
import unittest
import winreg
from unittest import mock

import diagnostics
import engine
import i18n
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
        "cpu": {"load": 12.0, "top": [("chrome.exe", 4.0)]},
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
        "update_settings": {"disabled": False, "policy_off": False},
        "windows": {"product": "Windows 11", "version": "25H2", "build": 26200, "edition": "Professional",
                    "update": 7000, "server": False, "media": True},
        "firmware": {"uefi": True, "secure_boot": True, "tpm": 2, "anti_cheat": False},
        "security": {"uac_off": False, "mitigations_off": False},
        "proxy": {"enabled": False, "server": "", "pac": ""},
        "hosts": {"entries": 0, "blocked": []},
    }


# Checks that have nothing to say about the healthy desktop above
SILENT = {"battery", "memory_test", "memory_integrity", "cpu_microcode", "x3d_cores", "gpu_preference",
          "rgb_software", "throttling", "media_pack"}


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
        worn = verdict("disk_health", wear=[{"id": "0", "wear": 95, "read_errors": None}])
        self.assertEqual((worn.severity, worn.line), ("warning", "ssd_worn"))
        self.assertEqual(self.severity("disk_health", wear=[{"id": "0", "wear": 100, "read_errors": None}]), "problem")
        self.assertEqual(verdict("disk_health", wear=[{"id": "0", "wear": 3, "read_errors": 2}]).line, "read_errors")
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
        # The one cmdlet with a changing verb only reports the health Windows has already recorded
        script = diagnostics.POWERSHELL_SCRIPT.replace("Repair-WindowsImage -Online -CheckHealth", "")
        cmdlets = set(re.findall(r"\b([A-Z][a-z]+)-([A-Z][A-Za-z]+)\b", script))
        changing = {"Set", "Remove", "Stop", "Start", "Restart", "Invoke", "Enable", "Disable", "Clear", "Add",
                    "Register", "Unregister", "Install", "Uninstall", "Update", "Rename", "Move", "Copy", "Out",
                    "Export", "Import", "Mount", "Dismount", "Suspend", "Resume", "Reset", "Repair", "Optimize",
                    "Initialize", "Format", "Grant", "Revoke", "Block", "Unblock", "Save", "Send", "Write", "Edit",
                    "Sync"}
        self.assertEqual({verb for verb, _ in cmdlets} & changing, set())
        self.assertEqual({noun for verb, noun in cmdlets if verb == "New"}, {"Object"})
        self.assertEqual(re.findall(r"New-Object\s+(?:-ComObject\s+)?([\w.]+)", diagnostics.POWERSHELL_SCRIPT),
                         ["Text.UTF8Encoding", "Microsoft.Update.AutoUpdate"])
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
            facts = diagnostics.gather(steps.append)
        self.assertEqual(steps, diagnostics.GROUPS)
        for key in ("memory", "cpu", "drives", "uptime", "startup", "hosts", "windows", "pool", "boot", "power",
                    "processor", "security", "firmware", "vc_runtime"):
            self.assertIn(key, facts)
        findings = diagnostics.evaluate(facts)
        self.assertGreater(len(findings), 30)
        render_all(findings)


class Texts(unittest.TestCase):
    def test_every_check_is_explained(self):
        for lang, texts in i18n.TEXTS.items():
            for check, group in diagnostics.CHECKS:
                title, details = texts["diag"][check]
                self.assertTrue(title, (lang, check))
                self.assertGreater(len(details), 150, (lang, check))
            for group in diagnostics.GROUPS:
                self.assertIn("diag_step_" + group, texts["ui"])
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

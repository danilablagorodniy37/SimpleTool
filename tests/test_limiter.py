"""Memory limiter: logic on a fake API and real Windows calls on the test's own child process."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

import engine
import limiter
from limiter import MB, Limiter, WindowsApi


class FakeApi:
    """Processes in memory: {pid: [name, bytes]}; denied lists the ones without access."""

    def __init__(self, procs):
        self.procs = {pid: [name, size * MB] for pid, (name, size) in procs.items()}
        self.denied = set()
        self.caps = {}
        self.calls = []

    def processes(self):
        return [(pid, name) for pid, (name, _) in self.procs.items()]

    def working_set(self, pid):
        if pid in self.denied or pid not in self.procs:
            return None
        return self.procs[pid][1]

    def trim(self, pid):
        self.calls.append(("trim", pid))
        self.procs[pid][1] //= 10
        return True

    def set_hard_limit(self, pid, limit):
        self.calls.append(("cap", pid, limit))
        self.caps[pid] = limit
        return True

    def clear_hard_limit(self, pid):
        self.calls.append(("uncap", pid))
        self.caps.pop(pid, None)
        return True


def config(*rules, enabled=True):
    return {"enabled": enabled, "interval": 5,
            "rules": [{"name": n, "limit_mb": l, "mode": m, "enabled": e} for n, l, m, e in rules]}


class LimiterLogic(unittest.TestCase):
    def setUp(self):
        self.api = FakeApi({100: ("chrome", 900), 101: ("chrome", 600), 102: ("chrome", 300),
                            200: ("discord", 400), 300: ("explorer", 2000), 400: ("notepad", 50)})

    def make(self, cfg):
        lim = Limiter(api=self.api, config=cfg)
        lim.own_pid = 1
        return lim

    def touched(self):
        return {call[1] for call in self.api.calls}

    def test_soft_trims_largest_first_and_stops_under_limit(self):
        lim = self.make(config(("chrome", 1000, "soft", True)))
        lim.cycle()
        self.assertEqual(self.api.calls, [("trim", 100), ("trim", 101)])  # 1800 -> 990 -> 450 MB, 300 untouched
        stat = lim.snapshot()["stats"]["chrome"]
        self.assertEqual(stat["count"], 3)
        self.assertLessEqual(stat["bytes"], 1000 * MB * limiter.SOFT_TARGET)
        self.assertEqual(stat["trims"], 2)
        self.assertGreater(lim.snapshot()["freed"], 0)

    def test_soft_does_nothing_under_limit(self):
        lim = self.make(config(("discord", 700, "soft", True)))
        lim.cycle()
        self.assertEqual(self.api.calls, [])

    def test_disabled_limiter_and_disabled_rule_do_nothing(self):
        self.make(config(("chrome", 100, "soft", True), enabled=False)).cycle()
        self.make(config(("chrome", 100, "soft", False))).cycle()
        self.assertEqual(self.api.calls, [])

    def test_hard_caps_each_process_and_releases_them(self):
        lim = self.make(config(("chrome", 500, "hard", True)))
        lim.cycle()
        self.assertEqual(self.api.caps, {100: 500 * MB, 101: 500 * MB, 102: 500 * MB})
        lim.cycle()  # caps are not set again
        self.assertEqual(sum(1 for c in self.api.calls if c[0] == "cap"), 3)
        lim.update(lambda c: c["rules"][0].update(mode="soft"), save=False)
        lim.cycle()
        self.assertEqual(self.api.caps, {}, "switching to soft mode removes the caps")

    def test_caps_released_when_rule_removed_disabled_or_stopped(self):
        lim = self.make(config(("chrome", 500, "hard", True), ("discord", 300, "hard", True)))
        lim.cycle()
        lim.update(lambda c: c["rules"].pop(0), save=False)
        lim.cycle()
        self.assertEqual(set(self.api.caps), {200})
        lim.update(lambda c: c.update(enabled=False), save=False)
        lim.cycle()
        self.assertEqual(self.api.caps, {})
        lim.update(lambda c: c.update(enabled=True), save=False)
        lim.cycle()
        lim.stop()
        self.assertEqual(self.api.caps, {}, "closing SimpleTool must not leave caps behind")

    def test_never_touches_other_or_protected_processes(self):
        cfg = config(("chrome", 100, "soft", True))
        cfg["rules"].append({"name": "explorer", "limit_mb": 100, "mode": "hard", "enabled": True})  # skips the checks
        lim = self.make(cfg)
        lim.cycle()
        self.assertNotIn(300, self.touched())
        self.assertNotIn(400, self.touched())
        self.assertNotIn(200, self.touched())

    def test_own_process_is_never_touched(self):
        lim = self.make(config(("chrome", 100, "hard", True)))
        lim.own_pid = 100
        lim.cycle()
        self.assertNotIn(100, self.touched())

    def test_denied_processes_are_counted_not_touched(self):
        self.api.denied = {100}
        lim = self.make(config(("chrome", 100, "soft", True)))
        lim.cycle()
        self.assertNotIn(100, self.touched())
        self.assertEqual(lim.snapshot()["stats"]["chrome"]["denied"], 1)

    def test_exited_processes_are_forgotten(self):
        lim = self.make(config(("chrome", 500, "hard", True)))
        lim.cycle()
        del self.api.procs[100]
        lim.cycle()
        self.assertNotIn(100, lim.capped)

    def test_reused_process_number_is_not_released(self):
        lim = self.make(config(("chrome", 500, "hard", True)))
        lim.cycle()
        self.api.procs[100][0] = "notepad"  # chrome exited, its process ID went to another program
        lim.cycle()
        lim.stop()
        self.assertNotIn(("uncap", 100), self.api.calls, "another program must not be touched")

    def test_background_thread_runs_and_stops(self):
        lim = self.make(config(("chrome", 1000, "soft", True)))
        lim.start()
        deadline = time.time() + 5
        while not self.api.calls and time.time() < deadline:
            time.sleep(0.05)
        lim.stop()
        self.assertTrue(self.api.calls)
        self.assertFalse(lim._thread.is_alive())


class LimiterConfig(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="simpletool-limiter-")
        self.patch = mock.patch.object(engine, "data_dir", lambda: self.tmp)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_round_trip_and_validation(self):
        with open(limiter.config_path(), "w", encoding="utf-8") as f:
            json.dump({"enabled": True, "interval": 999, "rules": [
                {"name": "Chrome.exe", "limit_mb": 5, "mode": "hard", "title": "  Google Chrome  "},
                {"name": "chrome", "limit_mb": 4000},          # duplicate
                {"name": "svchost", "limit_mb": 500},          # system process
                {"name": "discord", "limit_mb": "oops"},       # broken value
                {"limit_mb": 500},                            # no name
            ]}, f)
        cfg = limiter.load_config()
        self.assertEqual(cfg["interval"], limiter.DEFAULT_INTERVAL)
        self.assertEqual(cfg["rules"], [{"name": "chrome", "limit_mb": limiter.MIN_LIMIT_MB, "mode": "hard",
                                         "enabled": True, "title": "Google Chrome"}])
        limiter.save_config(cfg)
        self.assertEqual(limiter.load_config(), cfg)

    def test_missing_or_corrupt_file_gives_safe_defaults(self):
        self.assertEqual(limiter.load_config(), limiter.default_config())
        with open(limiter.config_path(), "w") as f:
            f.write("{broken")
        self.assertFalse(limiter.load_config()["enabled"])

    def test_names_and_protection(self):
        self.assertEqual(limiter.normalize(r"C:\Program Files\Google\Chrome.EXE"), "chrome")
        for name in ("explorer.exe", "svchost", "csrss", "lsass", "dwm", "SimpleTool.exe", "winlogon"):
            self.assertTrue(limiter.is_protected(name), name)
        for name in limiter.DEFAULT_LIMITS:
            self.assertFalse(limiter.is_protected(name), name)
        self.assertEqual(limiter.default_limit("Discord.exe"), 700)
        self.assertEqual(limiter.default_limit("pycharm64"), limiter.CUSTOM_LIMIT)

    def test_running_programs_hides_system_and_self(self):
        api = FakeApi({os.getpid(): ("chrome", 100), 10: ("svchost", 500), 11: ("discord", 300), 12: ("discord", 50)})
        self.assertEqual(limiter.running_programs(api), [("discord", 2, 350 * MB)])


@unittest.skipUnless(sys.platform == "win32", "Windows API")
class RealWindowsApi(unittest.TestCase):
    """Real Windows calls, only on a child process the test starts itself."""

    def setUp(self):
        code = ("b = bytearray(200 * 2**20)\nfor i in range(0, len(b), 4096): b[i] = 1\n"
                "print('ready', flush=True)\nimport time; time.sleep(60)")
        self.child = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
        self.assertEqual(self.child.stdout.readline().strip(), "ready")
        self.api = WindowsApi()

    def tearDown(self):
        self.child.kill()
        self.child.wait()
        self.child.stdout.close()

    def test_measure_trim_cap_and_uncap_child(self):
        pid = self.child.pid
        self.assertIn((pid, "python"), self.api.processes())
        before = self.api.working_set(pid)
        self.assertGreater(before, 150 * MB)
        self.assertTrue(self.api.trim(pid))
        self.assertLess(self.api.working_set(pid), before // 2)
        self.assertTrue(self.api.set_hard_limit(pid, 64 * MB))
        handle = self.api._open(pid, WindowsApi.QUERY)
        try:
            self.assertTrue(self.api._quota(handle)[2] & WindowsApi.MAX_ENABLE)
            self.assertTrue(self.api.clear_hard_limit(pid))
            self.assertTrue(self.api._quota(handle)[2] & WindowsApi.MAX_DISABLE)
        finally:
            self.api.k.CloseHandle(handle)
        self.assertIsNone(self.child.poll(), "the process must keep running")

    def test_missing_process_is_handled(self):
        self.assertIsNone(self.api.working_set(0xFFFFFFF0))
        self.assertFalse(self.api.trim(0xFFFFFFF0))
        self.assertFalse(self.api.clear_hard_limit(0xFFFFFFF0))


@unittest.skipUnless(sys.platform == "win32", "Windows API")
class RealLimiterEndToEnd(unittest.TestCase):
    """The whole limiter with real Windows calls. The target is a copy of python under a unique name
    that the test starts itself: no other process on the PC matches that name."""

    NAME = "simpletool-memtest"
    CHILD = ("import sys\nb = bytearray(300 * 2**20)\n"
             "def touch():\n    for i in range(0, len(b), 4096): b[i] = (b[i] + 1) % 256\n"
             "touch()\nprint('ready', flush=True)\n"
             "for line in sys.stdin:\n    touch()\n    print('touched', flush=True)\n")

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="simpletool-memtest-")
        base = sys.base_prefix  # not the venv python: that one starts the real python.exe as a child process
        shutil.copy(os.path.join(base, "python.exe"), os.path.join(self.dir, self.NAME + ".exe"))
        for name in os.listdir(base):
            if name.lower().endswith(".dll"):
                shutil.copy(os.path.join(base, name), self.dir)
        env = dict(os.environ, PYTHONHOME=base)
        env.pop("PYTHONPATH", None)
        self.child = subprocess.Popen([os.path.join(self.dir, self.NAME + ".exe"), "-c", self.CHILD], env=env,
                                      stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        self.assertEqual(self.child.stdout.readline().strip(), "ready")

    def tearDown(self):
        self.child.kill()
        self.child.wait()
        self.child.stdin.close()
        self.child.stdout.close()
        shutil.rmtree(self.dir, ignore_errors=True)

    def touch(self):
        self.child.stdin.write("go\n")
        self.child.stdin.flush()
        self.assertEqual(self.child.stdout.readline().strip(), "touched")

    def test_soft_then_hard_limit(self):
        pid = self.child.pid
        lim = Limiter(api=WindowsApi(), config=config((self.NAME, 100, "soft", True)))
        api = lim.api
        self.assertGreater(api.working_set(pid), 250 * MB)

        lim.cycle()  # soft: the program is over the limit, so its memory is trimmed
        stat = lim.snapshot()["stats"][self.NAME]
        self.assertEqual(stat["count"], 1)
        self.assertGreater(stat["freed"], 150 * MB)
        self.assertLess(api.working_set(pid), 100 * MB)

        lim.update(lambda c: c["rules"][0].update(mode="hard"), save=False)
        lim.cycle()  # hard: even when the process touches all 300 MB again, it stays within the limit in RAM
        self.assertIn(pid, lim.capped)
        self.touch()
        self.assertLess(api.working_set(pid), 110 * MB)

        lim.stop()  # exiting SimpleTool removes the cap, and the process can use all its memory again
        self.assertEqual(lim.capped, {})
        self.touch()
        self.assertGreater(api.working_set(pid), 250 * MB)
        self.assertIsNone(self.child.poll(), "the process must keep running")


if __name__ == "__main__":
    unittest.main()

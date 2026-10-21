"""Installing an update: only SimpleTool's own releases, only a file that matches its SHA-256, and the running
version comes back if anything fails. No network: downloads are fake, files live in a temporary folder."""
import hashlib
import io
import os
import shutil
import tempfile
import unittest
from unittest import mock

import updater

URL = "https://github.com/danilablagorodniy37/SimpleTool/releases/download/v0.6.3/SimpleTool.exe"
NEW = b"MZ new SimpleTool" * 1000
SHA = hashlib.sha256(NEW).hexdigest()


class Answer(io.BytesIO):
    headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def serving(body):
    return mock.patch.object(updater.urllib.request, "urlopen", lambda request, timeout: Answer(body))


class Updater(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="simpletool-update-")
        self.exe = os.path.join(self.dir, "SimpleTool.exe")
        with open(self.exe, "wb") as f:
            f.write(b"MZ old SimpleTool")
        self.frozen = mock.patch.object(updater, "target", lambda: self.exe)
        self.frozen.start()

    def tearDown(self):
        self.frozen.stop()
        shutil.rmtree(self.dir, ignore_errors=True)

    def read(self, path):
        with open(path, "rb") as f:
            return f.read()

    def info(self, **changes):
        return dict({"version": "0.6.3", "url": URL, "sha256": SHA, "size": len(NEW)}, **changes)

    def test_install(self):
        seen = []
        with serving(NEW):
            started = updater.install(self.info(), lambda done, total: seen.append((done, total)))
        self.assertEqual(started, self.exe)
        self.assertEqual(self.read(self.exe), NEW)
        self.assertEqual(self.read(self.exe + ".old"), b"MZ old SimpleTool", "kept until the new one deletes it")
        self.assertFalse(os.path.exists(self.exe + ".new"))
        self.assertEqual(seen[-1], (len(NEW), len(NEW)))
        self.assertTrue(updater.cleanup())
        self.assertFalse(os.path.exists(self.exe + ".old"))

    def test_a_file_that_does_not_match_is_not_installed(self):
        for body, info in ((b"MZ something else", self.info()), (NEW, self.info(size=len(NEW) + 1))):
            with self.subTest(size=info["size"]), serving(body), self.assertRaises(updater.UpdateFailed):
                updater.install(info)
            self.assertEqual(self.read(self.exe), b"MZ old SimpleTool")
            self.assertFalse(os.path.exists(self.exe + ".new"))

    def test_only_simpletool_releases_with_a_checksum(self):
        for info in (self.info(url="https://example.com/SimpleTool.exe"), self.info(sha256=None),
                     self.info(url=None)):
            self.assertFalse(updater.can_install(info))
            with self.assertRaises(updater.UpdateFailed):
                updater.install(info)
        self.assertTrue(updater.can_install(self.info()))
        with mock.patch.object(updater, "target", lambda: None):
            self.assertFalse(updater.can_install(self.info()), "run from the source code")

    def test_a_failed_download_leaves_nothing(self):
        def offline(request, timeout):
            raise updater.urllib.error.URLError("getaddrinfo failed")
        with mock.patch.object(updater.urllib.request, "urlopen", offline), self.assertRaises(updater.UpdateFailed):
            updater.install(self.info())
        self.assertEqual(sorted(os.listdir(self.dir)), ["SimpleTool.exe"])

    def test_the_running_version_comes_back_if_the_swap_fails(self):
        real = os.replace
        calls = []

        def replace(src, dst):
            calls.append((src, dst))
            if src.endswith(".new"):
                raise PermissionError(5, "Access is denied")
            return real(src, dst)

        with serving(NEW), mock.patch.object(updater.os, "replace", replace), \
                self.assertRaises(updater.UpdateFailed):
            updater.install(self.info())
        self.assertEqual(self.read(self.exe), b"MZ old SimpleTool")
        self.assertEqual(sorted(os.listdir(self.dir)), ["SimpleTool.exe"])


if __name__ == "__main__":
    unittest.main()

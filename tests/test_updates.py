"""Checking for updates: the version comparison and every way the website's answer can go wrong. No network."""
import io
import json
import unittest
import urllib.error
from unittest import mock

import updates

EXE = "https://github.com/danilablagorodniy37/SimpleTool/releases/download/v0.7/SimpleTool.exe"
NOTES = "https://github.com/danilablagorodniy37/SimpleTool/releases/tag/v0.7"


class Answer(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def answering(body):
    data = body if isinstance(body, bytes) else json.dumps(body).encode()
    return mock.patch.object(updates.urllib.request, "urlopen", lambda request, timeout: Answer(data))


def failing(exc):
    def urlopen(request, timeout):
        raise exc
    return mock.patch.object(updates.urllib.request, "urlopen", urlopen)


class Versions(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(updates.parse_version("0.6.1"), (0, 6, 1))
        self.assertEqual(updates.parse_version("0.6.0"), updates.parse_version("0.6"))
        self.assertEqual(updates.parse_version("1"), (1,))
        for bad in ("", "v0.6", "0.6-beta", "0..6", "0.6.", None, 6, "1.2.3.4.5"):
            self.assertIsNone(updates.parse_version(bad), bad)

    def test_order(self):
        self.assertLess(updates.parse_version("0.6"), updates.parse_version("0.6.1"))
        self.assertLess(updates.parse_version("0.6.1"), updates.parse_version("0.10"))
        self.assertLess(updates.parse_version("0.9.9"), updates.parse_version("1.0"))


class Check(unittest.TestCase):
    def test_newer_version(self):
        with answering({"ok": True, "version": "0.7", "url": EXE, "page": NOTES}):
            self.assertEqual(updates.check("0.6.1"), {"version": "0.7", "newer": True, "url": EXE, "page": NOTES,
                                                      "sha256": None, "size": None})
        with answering({"ok": True, "version": "0.7", "url": EXE, "sha256": "AB" * 32, "size": 12363139}):
            info = updates.check("0.6.1")
        self.assertEqual((info["sha256"], info["size"]), ("ab" * 32, 12363139))
        with answering({"ok": True, "version": "0.7", "sha256": "not a hash", "size": -1}):
            info = updates.check("0.6.1")
        self.assertEqual((info["sha256"], info["size"]), (None, None))

    def test_same_or_older_version(self):
        for latest in ("0.6.1", "0.6.1.0", "0.6"):
            with answering({"ok": True, "version": latest, "url": EXE}):
                self.assertFalse(updates.check("0.6.1")["newer"], latest)

    def test_the_request_names_the_version_and_nothing_else(self):
        seen = {}

        def urlopen(request, timeout):
            seen["url"], seen["headers"], seen["data"] = request.full_url, dict(request.header_items()), request.data
            return Answer(json.dumps({"ok": True, "version": "0.6.1"}).encode())

        with mock.patch.object(updates.urllib.request, "urlopen", urlopen):
            updates.check("0.6.1")
        self.assertEqual(seen["url"], "https://blagotech.uk/api/simpletool")
        self.assertIsNone(seen["data"])
        self.assertEqual(seen["headers"]["User-agent"], "SimpleTool/0.6.1")

    def test_only_trusted_addresses_are_opened(self):
        with answering({"ok": True, "version": "0.7", "url": "https://evil.example/SimpleTool.exe",
                        "page": "http://github.com/danilablagorodniy37/SimpleTool/"}):
            info = updates.check("0.6.1")
        self.assertIsNone(info["url"])
        self.assertIsNone(info["page"])

    def test_bad_answers(self):
        for body in (b"<html>", b"[]", {"ok": False}, {"ok": True}, {"ok": True, "version": "latest"},
                     {"ok": "true", "version": "0.7"}, b"{" + b" " * (updates.MAX_ANSWER + 1) + b"}"):
            with self.subTest(body=str(body)[:40]), answering(body), self.assertRaises(updates.CheckFailed):
                updates.check("0.6.1")

    def test_network_failures(self):
        for exc in (urllib.error.URLError("getaddrinfo failed"), TimeoutError("timed out"),
                    urllib.error.HTTPError(updates.LATEST_URL, 502, "Bad Gateway", {}, None),
                    ConnectionResetError(10054, "reset")):
            with self.subTest(exc=exc), failing(exc), self.assertRaises(updates.CheckFailed):
                updates.check("0.6.1")


if __name__ == "__main__":
    unittest.main()

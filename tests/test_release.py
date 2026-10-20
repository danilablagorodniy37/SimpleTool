"""Releases: the changelog describes the version being released, and the release notes are put together right."""
import hashlib
import os
import tempfile
import unittest

import build
from tools import release_notes

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Release(unittest.TestCase):
    def test_changelog_describes_this_version(self):
        # A tag of a version without a changelog section stops the release workflow: better to know before
        with open(release_notes.CHANGELOG, encoding="utf-8") as f:
            self.assertGreater(len(release_notes.section(build.app_version(), f.read())), 40,
                               f"write a '## {build.app_version()}' section in CHANGELOG.md")

    def test_sections_do_not_run_into_each_other(self):
        text = "# Changelog\n\n## 0.6.1\n\n- new\n\n## 0.6\n\n- old\n"
        self.assertEqual(release_notes.section("0.6.1", text), "- new")
        self.assertEqual(release_notes.section("0.6", text), "- old")
        self.assertEqual(release_notes.section("0.5", text), "")

    def test_notes_carry_the_hash_of_the_exe(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"not really an exe")
        try:
            notes = release_notes.render(build.app_version(), f.name)
        finally:
            os.remove(f.name)
        self.assertIn(f"SHA-256: `{hashlib.sha256(b'not really an exe').hexdigest()}`", notes)
        self.assertIn(f"## What's new in {build.app_version()}", notes)
        self.assertIn("service@blagotech.uk", notes)

    def test_the_workflow_publishes_what_the_website_reads(self):
        # The website's button, its counter and the update check all look for SimpleTool.exe in the latest
        # release that is not a prerelease
        with open(os.path.join(ROOT, ".github", "workflows", "release.yml"), encoding="utf-8") as f:
            workflow = f.read()
        self.assertIn("dist/SimpleTool.exe dist/THIRD-PARTY-NOTICES.txt", workflow)
        self.assertNotIn("--prerelease", workflow)
        self.assertNotIn("--draft", workflow)


if __name__ == "__main__":
    unittest.main()

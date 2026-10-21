"""What's new: every version's notes are complete, and the right versions are shown after an update."""
import unittest
from unittest import mock

import build
import i18n
import whatsnew


class WhatsNew(unittest.TestCase):
    def test_this_version_has_notes_in_every_language(self):
        version = build.app_version()
        self.assertIn(version, whatsnew.NOTES, "write the What's new notes of this version in whatsnew.py")
        for notes in whatsnew.NOTES.values():
            for lang in i18n.TEXTS:
                self.assertTrue(notes[lang] and all(len(line) > 20 for line in notes[lang]), lang)
                self.assertEqual(len(notes[lang]), len(notes["en"]), lang)

    def test_versions_shown_after_an_update(self):
        notes = {"0.6.2": {"en": ["a"]}, "0.7": {"en": ["b"]}, "0.8": {"en": ["c"]}}
        with mock.patch.object(whatsnew, "NOTES", notes):
            self.assertEqual([v for v, _ in whatsnew.since("0.6.2", "0.8")], ["0.8", "0.7"])
            self.assertEqual([v for v, _ in whatsnew.since("0.6.1", "0.7")], ["0.7", "0.6.2"])
            self.assertEqual([v for v, _ in whatsnew.since(None, "0.7")], ["0.7"], "unknown: this version only")
            self.assertEqual(whatsnew.since("0.8", "0.8"), [])
            self.assertEqual(whatsnew.since("0.7", "0.7.1"), [], "no notes for a version: nothing to show")


if __name__ == "__main__":
    unittest.main()

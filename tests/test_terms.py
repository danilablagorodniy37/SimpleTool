"""The terms of use: complete in every language, and TERMS.md matches what SimpleTool shows."""
import os
import unittest

import i18n
import terms
from tools import terms_md


class Terms(unittest.TestCase):
    def test_every_language_has_the_same_terms(self):
        english = terms.TERMS["en"]
        for lang in i18n.TEXTS:
            text = terms.TERMS[lang]
            with self.subTest(lang=lang):
                self.assertEqual(set(text), set(english))
                self.assertEqual(len(text["sections"]), len(english["sections"]))
                for heading, body in text["sections"]:
                    self.assertTrue(heading and len(body) > 40, heading)
                self.assertIn("service@blagotech.uk", text["sections"][-1][1])

    def test_terms_md_is_up_to_date(self):
        with open(terms_md.PATH, encoding="utf-8") as f:
            self.assertEqual(f.read(), terms_md.render(), "run python tools/terms_md.py")

    def test_terms_json_is_up_to_date(self):
        # The website copies its terms page from terms.json
        with open(terms_md.JSON_PATH, encoding="utf-8") as f:
            self.assertEqual(f.read(), terms_md.render_json(), "run python tools/terms_md.py")

    def test_terms_md_ships_with_the_repository(self):
        self.assertTrue(os.path.exists(terms_md.PATH))

"""Тексты на трёх языках: все ключи и подстановки на месте, иначе при смене языка окно упадёт."""
import re
import string
import unittest

import i18n
import services
import tweaks

EN = i18n.TEXTS["en"]


def placeholders(text):
    return {name for _, name, _, _ in string.Formatter().parse(text) if name is not None}


class Texts(unittest.TestCase):
    def test_every_language_has_every_key(self):
        for lang, texts in i18n.TEXTS.items():
            for section, entries in EN.items():
                with self.subTest(lang=lang, section=section):
                    self.assertEqual(set(entries), set(texts[section]))

    def test_placeholders_match_english(self):
        for lang, texts in i18n.TEXTS.items():
            for section in ("ui", "menu"):
                for key, text in EN[section].items():
                    with self.subTest(lang=lang, key=key):
                        self.assertEqual(placeholders(texts[section][key]), placeholders(text))

    def test_tweak_and_service_texts_are_complete(self):
        for lang, texts in i18n.TEXTS.items():
            for tweak in tweaks.TWEAKS:
                name, short, details = texts["tweaks"][tweak.id]
                with self.subTest(lang=lang, tweak=tweak.id):
                    self.assertTrue(name and short)
                    self.assertGreater(len(details), 150, "detailed explanation expected")
            for _, name, _ in services.SERVICES:
                title, details = texts["services"][name]
                self.assertTrue(title and len(details) > 60, (lang, name))
            for category in tweaks.CATEGORIES + ["overview", "memory", "snapshots"]:
                self.assertEqual(len(texts["categories"][category]), 2)

    def test_menu_labels_exist_for_every_language(self):
        for tweak in tweaks.TWEAKS:
            for op in tweak.ops:
                if callable(getattr(op, "data", None)):
                    for lang in i18n.TEXTS:
                        self.assertTrue(op.data(lang), (tweak.id, lang))

    def test_status_and_kind_keys_exist(self):
        for lang, texts in i18n.TEXTS.items():
            ui = texts["ui"]
            for state in ("applied", "partial", "not_applied", "unavailable", "admin", "checking", "unknown"):
                self.assertIn("status_" + state, ui)
            for kind in ("initial", "before_apply", "before_revert", "before_restore", "manual"):
                self.assertIn("kind_" + kind, ui)
            for reason in ("access_denied", "scm_unavailable", "tasks_unavailable", "error"):
                self.assertEqual(len(texts["reasons"][reason]), 2)

    def test_product_is_named_simpletool_only(self):
        """Продукт называется SimpleTool: интерфейс не называет другие программы-твикеры."""
        for lang, texts in i18n.TEXTS.items():
            blob = repr(texts)
            self.assertNotRegex(blob, r"(?i)tweaker", lang)


if __name__ == "__main__":
    unittest.main()

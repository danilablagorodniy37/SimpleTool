"""Explorer restart: only the read-only part runs in tests (the restart itself closes the user's folder windows)."""
import unittest

import engine
import main


class ExplorerRestart(unittest.TestCase):
    def test_explorer_processes_of_this_session_are_listed(self):
        pids = engine.explorer_pids()
        self.assertIsInstance(pids, list)
        for pid in pids:
            self.assertIsInstance(pid, int)
            self.assertGreater(pid, 0)

    def test_effect_texts_after_apply(self):
        self.assertEqual(main.effect_keys(set()), [])
        self.assertEqual(main.effect_keys({"explorer"}), ["after_explorer"])
        self.assertEqual(main.effect_keys({"signout"}), ["after_signout"])
        self.assertEqual(main.effect_keys({"signout", "restart"}), ["after_restart"])
        self.assertEqual(main.effect_keys({"explorer", "restart", "signout"}), ["after_explorer", "after_restart"])


if __name__ == "__main__":
    unittest.main()

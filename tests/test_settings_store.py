import unittest
from core.settings_store import AppSettings, SettingsStore
import tempfile, pathlib


class AdvancedPanelSettingTests(unittest.TestCase):
    def test_defaults_to_false(self):
        s = AppSettings()
        self.assertFalse(s.show_advanced_panel)

    def test_round_trips_through_json(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "settings.json"
            store = SettingsStore(path)
            from dataclasses import replace
            store.save(replace(store.get(), show_advanced_panel=True))
            store2 = SettingsStore(path)
            self.assertTrue(store2.get().show_advanced_panel)


if __name__ == "__main__":
    unittest.main()

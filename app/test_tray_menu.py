"""Tray interactions must preserve colour and use the shared command queue."""
import os
import unittest
from unittest.mock import Mock
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication, QMainWindow
from core import Controller
from desktop import Window
from light_features import scene_options
from test_core import MemoryStore
from tray_menu import TrayMenu, state_label


class TrayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = QMainWindow()
        self.store = MemoryStore()
        self.store.config["devices"][1]["name"] = "Lampe RGB"
        self.window.controller = Controller(self.store, demo=True)
        self.window.device_states = {"a60": {"power": True, "mode": "colour", "brightness": 72,
            "hsv": {"h": 245, "s": 36, "v": 72}, "scenes": scene_options(True)}}
        for name in ("open_window", "command", "group", "refresh", "lsc_login", "quit"):
            setattr(self.window, name, Mock())
        self.menu = TrayMenu(self.window)

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def rgb_menu(self):
        return next(action.menu() for action in self.menu.actions() if action.text() == "Lampe RGB")

    def test_opening_menu_reads_names_without_sending_commands(self):
        self.menu.rebuild()
        self.assertEqual(self.rgb_menu().actions()[0].text(), "Allumée · couleur")
        self.window.command.assert_not_called()

    def test_brightness_preserves_hue_and_saturation(self):
        submenu = next(action.menu() for action in self.rgb_menu().actions() if action.text() == "Luminosité")
        next(action for action in submenu.actions() if action.text() == "25 %").trigger()
        self.window.command.assert_called_once_with("a60", "hsv", {"h": 245, "s": 36, "v": 25})
        self.assertEqual(self.window.device_states["a60"]["hsv"]["v"], 72)

    def test_brightness_uses_latest_state_when_clicked(self):
        self.window.device_states["a60"] = {"mode": "white"}
        self.menu.brightness("a60", 50)
        self.window.command.assert_called_once_with("a60", "brightness", 50)

    def test_unknown_scene_and_offline_states_do_not_send_brightness(self):
        for state in ({}, {"mode": "scene"}, {"mode": "colour"},
                      {"mode": "white", "online": False}, {"mode": "white", "error": "Network"}):
            self.window.device_states["a60"] = state
            self.menu.brightness("a60", 25)
        self.window.command.assert_not_called()

    def test_received_scene_and_correct_bulb_are_forwarded(self):
        scene = dict(scene_options(True)[0], data="000e0d00000000000000012c0000", received=True)
        self.window.device_states["a60"]["scenes"] = [scene]
        self.menu.rebuild()
        scenes = next(action.menu() for action in self.rgb_menu().actions() if action.text() == "Scènes")
        scenes.actions()[0].trigger()
        self.window.command.assert_called_once_with("a60", "scene", scene["data"])

    def test_cct_has_no_colour_presets(self):
        cct = self.menu.actions()[2].menu()
        self.assertFalse(any(action.text().startswith("Couleurs") for action in cct.actions()))

    def test_offline_label_does_not_describe_cached_power_as_current(self):
        self.assertEqual(state_label({"online": False, "power": True}), "Hors ligne")
        self.assertEqual(state_label({"error": "Timeout"}), "État indisponible")


class QueueTests(unittest.TestCase):
    def test_group_commands_are_retained_while_read_is_busy(self):
        from collections import OrderedDict
        window = Mock()
        window.busy = True
        window.pending_commands = OrderedDict()
        window.cards = {"a65": object(), "a60": object()}
        window.command = lambda *args: Window.command(window, *args)
        Window.group(window, True)
        self.assertEqual(list(window.pending_commands.items()), [
            (("a65", "power"), True), (("a60", "power"), True)])
        window.submit.assert_not_called()


if __name__ == "__main__":
    unittest.main()

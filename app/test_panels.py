"""Interaction tests for readback versus user commands; no real devices."""
import os
import unittest
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from panels import LampCard
from core import DEFAULTS


class FakeWindow:
    def __init__(self): self.commands = []
    def command(self, slot, action, value): self.commands.append((slot, action, value))


class PanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = FakeWindow()
        self.card = LampCard(DEFAULTS[1], self.window)
        self.card.resize(410, 570)
        self.card.show()
        self.app.processEvents()

    def tearDown(self):
        self.card.close()
        self.card.deleteLater()
        self.app.processEvents()

    def test_external_readback_updates_all_colour_controls_without_writing(self):
        self.card.show_state({'power': True, 'mode': 'colour', 'brightness': 72,
                              'temperature': 20, 'hsv': {'h': 240, 's': 35, 'v': 72}})
        self.assertEqual(self.card.tabs.currentIndex(), 1)
        self.assertEqual(self.card.colour_ring.value, 240)
        self.assertEqual(self.card.saturation.value(), 35)
        self.assertEqual(self.card.colour_brightness.value(), 72)
        self.assertEqual(self.window.commands, [])

    def test_colour_drag_sends_one_command_on_release(self):
        self.card.show_state({'power': True, 'mode': 'colour', 'hsv': {'h': 0, 's': 25, 'v': 80}})
        self.app.processEvents()
        ring = self.card.colour_ring
        centre, radius = ring.geometry_values()
        right = QPoint(round(centre.x()+radius), round(centre.y()))
        left = QPoint(round(centre.x()-radius), round(centre.y()))
        QTest.mousePress(ring, Qt.MouseButton.LeftButton, pos=right)
        QTest.mouseMove(ring, left)
        self.assertEqual(self.window.commands, [])
        QTest.mouseRelease(ring, Qt.MouseButton.LeftButton, pos=left)
        self.assertEqual(len(self.window.commands), 1)
        slot, action, value = self.window.commands[0]
        self.assertEqual((slot, action), ('a60', 'hsv'))
        # Mouse positions have integer pixels; the ring centre can be half a pixel.
        self.assertAlmostEqual(value['h'], 180, delta=1)
        self.assertEqual((value['s'], value['v']), (25, 80))

    def test_readback_does_not_interrupt_an_unfinished_drag(self):
        self.card.colour_ring.dragging = True
        self.card.colour_ring.value = 120
        self.card.show_state({'power': True, 'mode': 'colour', 'hsv': {'h': 240, 's': 50, 'v': 70}})
        self.assertEqual(self.card.colour_ring.value, 120)
        self.assertEqual(self.window.commands, [])

    def test_cct_has_no_colour_controls(self):
        card = LampCard(DEFAULTS[0], self.window)
        self.assertEqual(card.tabs.count(), 2)
        self.assertEqual(card.tabs.tabText(1), 'Scène')
        self.assertFalse(hasattr(card, 'colour_ring'))
        card.deleteLater()

    def test_white_change_is_a_single_queued_command(self):
        self.card.white_ring.value=25
        self.card.white_brightness.setValue(40)
        self.card.send_white()
        self.assertEqual(self.window.commands,[('a60','white',{'temperature':25,'brightness':40})])

    def test_scene_readback_checks_button_without_command(self):
        from light_features import scene_options
        scene=scene_options(True)[0]
        self.card.show_state({'power':True,'mode':'scene','scene_data':scene['data']})
        self.assertEqual(self.window.commands,[])
        self.assertTrue(self.card.scene_panel.buttons[0][1].isChecked())

    def test_countdown_invalid_duration_does_not_send(self):
        from feature_panels import Countdown
        dialog=Countdown(self.card)
        dialog.set_duration(0)
        dialog.start()
        self.assertEqual(self.window.commands,[])
        dialog.reject()

    def test_countdown_start_and_cancel_use_device_timer(self):
        from feature_panels import Countdown
        dialog=Countdown(self.card)
        dialog.set_duration(300)
        dialog.start()
        dialog.send(0)
        self.assertEqual(self.window.commands,[('a60','countdown',300),('a60','countdown',0)])
        dialog.reject()


if __name__ == '__main__':
    unittest.main()

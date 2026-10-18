"""Regression for replacing numbers by clicking, without first deleting them."""
import os
import unittest
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from PySide6.QtCore import QPoint, QTime, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QAbstractSpinBox
from time_inputs import DurationInput, TimeInput


class TimeInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def click_digit(self, field, position):
        edit = field.lineEdit()
        y = edit.height()//2
        pixels = [x for x in range(edit.width()) if edit.cursorPositionAt(QPoint(x,y))==position]
        self.assertTrue(pixels)
        QTest.mouseClick(edit,Qt.MouseButton.LeftButton,pos=QPoint(pixels[len(pixels)//2],y))

    def prepare(self, field):
        self.addCleanup(field.close)
        field.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        field.setAlignment(Qt.AlignmentFlag.AlignCenter)
        field.resize(230,70)
        field.show()
        self.app.processEvents()

    def test_duration_click_replaces_existing_digits_even_when_already_focused(self):
        field = DurationInput()
        field.setRange(0,59)
        field.setValue(15)
        self.prepare(field)
        for value in ("30","08","45"):
            self.click_digit(field,1)
            self.assertEqual(field.lineEdit().selectedText(),field.text())
            QTest.keyClicks(field,value)
            self.assertEqual(field.value(),int(value))

    def test_time_click_replaces_hours_and_minutes_independently(self):
        field = TimeInput(QTime(6,5))
        field.setDisplayFormat("HH:mm")
        self.prepare(field)
        for position,text,expected in ((1,"08",QTime(8,5)),(4,"30",QTime(8,30)),
                                       (1,"12",QTime(12,30)),(4,"45",QTime(12,45))):
            self.click_digit(field,position)
            self.assertEqual(len(field.lineEdit().selectedText()),2)
            QTest.keyClicks(field,text)
            self.assertEqual(field.time(),expected)


if __name__ == "__main__":
    unittest.main()

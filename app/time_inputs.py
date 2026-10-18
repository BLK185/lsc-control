"""Numeric fields where a click selects the value to replace."""
from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QSpinBox, QTimeEdit


class ClickSelection(QObject):
    def __init__(self, field, select):
        super().__init__(field)
        self.select = select
        field.lineEdit().installEventFilter(self)

    def eventFilter(self, edit, event):
        if event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
            # Finish Qt's click handling before replacing its caret selection.
            edit.mouseReleaseEvent(event)
            self.select()
            return True
        return super().eventFilter(edit,event)


class DurationInput(QSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selection = ClickSelection(self,self.selectAll)

    def textFromValue(self, value):
        return f"{value:02d}"

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.selectAll()


class TimeInput(QTimeEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args,**kwargs)
        self.selection = ClickSelection(self,self.select_section)

    def select_section(self):
        self.setSelectedSection(self.currentSection())

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.select_section()

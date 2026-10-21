"""Direct positioning with native Qt geometry, keyboard support and drag signals."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSlider, QStyle, QStyleOptionSlider


class DirectSlider(QSlider):
    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._drag_offset = 0.0
        self.setMinimumHeight(28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _geometry(self):
        option = QStyleOptionSlider()
        self.initStyleOption(option)
        style = self.style()
        groove = style.subControlRect(QStyle.ComplexControl.CC_Slider, option,
                                      QStyle.SubControl.SC_SliderGroove, self)
        handle = style.subControlRect(QStyle.ComplexControl.CC_Slider, option,
                                      QStyle.SubControl.SC_SliderHandle, self)
        return option, groove, handle

    def _choose(self, position):
        option, groove, handle = self._geometry()
        span = max(0, groove.width() - handle.width())
        pixel = round(position.x() - self._drag_offset - groove.x() - (handle.width() - 1) // 2)
        value = QStyle.sliderValueFromPosition(self.minimum(), self.maximum(),
                                               pixel, span, option.upsideDown)
        self.setSliderPosition(value)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        _, _, handle = self._geometry()
        on_handle = handle.contains(event.position().toPoint())
        # Preserve the grab point on the thumb; a track click centres it immediately.
        self._drag_offset = event.position().x() - handle.center().x() if on_handle else 0.0
        self.setSliderDown(True)
        if not on_handle:
            self._choose(event.position())
        event.accept()

    def mouseMoveEvent(self, event):
        if self.isSliderDown():
            self._choose(event.position())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.isSliderDown():
            self._choose(event.position())
            self.setSliderDown(False)
            event.accept()
        else:
            event.ignore()

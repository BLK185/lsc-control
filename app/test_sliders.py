"""Mouse gestures must use the whole track and remain aligned with the thumb."""
import os
import unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QPoint,Qt
from PySide6.QtTest import QTest,QSignalSpy
from PySide6.QtWidgets import QApplication,QStyle,QStyleOptionSlider
from sliders import DirectSlider
from panels import LampCard
from core import DEFAULTS
from test_panels import FakeWindow


def handle_rect(slider):
    option=QStyleOptionSlider();slider.initStyleOption(option)
    return slider.style().subControlRect(QStyle.ComplexControl.CC_Slider,option,QStyle.SubControl.SC_SliderHandle,slider)


class SliderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.slider=DirectSlider();self.slider.setRange(0,100)
        self.slider.resize(360,32);self.slider.show();self.app.processEvents()

    def tearDown(self):
        self.slider.close();self.slider.deleteLater();self.app.processEvents()

    def test_track_click_positions_immediately_instead_of_page_stepping(self):
        self.slider.setValue(0)
        released=QSignalSpy(self.slider.sliderReleased)
        point=QPoint(270,16)
        QTest.mousePress(self.slider,Qt.MouseButton.LeftButton,pos=point)
        self.assertAlmostEqual(self.slider.value(),75,delta=2)
        self.assertTrue(self.slider.isSliderDown())
        self.assertEqual(released.count(),0)
        QTest.mouseRelease(self.slider,Qt.MouseButton.LeftButton,pos=point)
        self.assertFalse(self.slider.isSliderDown())
        self.assertEqual(released.count(),1)

    def test_click_outside_small_handle_on_taller_hit_area_starts_drag(self):
        self.slider.setValue(0)
        point=QPoint(180,2)
        QTest.mouseClick(self.slider,Qt.MouseButton.LeftButton,pos=point)
        self.assertAlmostEqual(self.slider.value(),50,delta=1)

    def test_thumb_follows_mouse_for_different_sizes_and_styles(self):
        for width in (180,360,640):
            for css in ('','QSlider::groove:horizontal {height:6px;} QSlider::handle:horizontal {width:26px;margin:-10px 0;}'):
                with self.subTest(width=width,css=bool(css)):
                    self.slider.setStyleSheet(css);self.slider.resize(width,36);self.app.processEvents()
                    QTest.mousePress(self.slider,Qt.MouseButton.LeftButton,pos=QPoint(width//2,18))
                    for fraction in (.15,.35,.80,.60):
                        point=QPoint(round(width*fraction),18)
                        QTest.mouseMove(self.slider,point)
                        self.assertAlmostEqual(handle_rect(self.slider).center().x(),point.x(),delta=width/200+1)
                    QTest.mouseRelease(self.slider,Qt.MouseButton.LeftButton,pos=point)

    def test_handle_grab_keeps_offset_without_jumping(self):
        self.slider.setValue(40)
        rect=handle_rect(self.slider)
        point=QPoint(rect.left()+2,rect.center().y())
        QTest.mousePress(self.slider,Qt.MouseButton.LeftButton,pos=point)
        self.assertEqual(self.slider.value(),40)
        destination=point+QPoint(90,0)
        QTest.mouseMove(self.slider,destination)
        self.assertAlmostEqual(self.slider.value(),66,delta=2)
        QTest.mouseRelease(self.slider,Qt.MouseButton.LeftButton,pos=destination)

    def test_drag_outside_track_clamps_and_releases_once(self):
        released=QSignalSpy(self.slider.sliderReleased)
        QTest.mousePress(self.slider,Qt.MouseButton.LeftButton,pos=QPoint(180,16))
        QTest.mouseMove(self.slider,QPoint(450,80))
        self.assertEqual(self.slider.value(),100)
        QTest.mouseMove(self.slider,QPoint(-50,80))
        self.assertEqual(self.slider.value(),0)
        QTest.mouseRelease(self.slider,Qt.MouseButton.LeftButton,pos=QPoint(-50,80))
        self.assertEqual(released.count(),1)
        self.assertFalse(self.slider.isSliderDown())

    def test_endpoints_and_reversed_layouts(self):
        for rtl,inverted in ((False,False),(True,False),(False,True),(True,True)):
            with self.subTest(rtl=rtl,inverted=inverted):
                self.slider.setLayoutDirection(Qt.LayoutDirection.RightToLeft if rtl else Qt.LayoutDirection.LeftToRight)
                self.slider.setInvertedAppearance(inverted)
                reverse=rtl != inverted
                QTest.mouseClick(self.slider,Qt.MouseButton.LeftButton,pos=QPoint(1,16))
                self.assertEqual(self.slider.value(),100 if reverse else 0)
                QTest.mouseClick(self.slider,Qt.MouseButton.LeftButton,pos=QPoint(359,16))
                self.assertEqual(self.slider.value(),0 if reverse else 100)

    def test_non_left_click_does_not_change_value(self):
        self.slider.setValue(25)
        QTest.mouseClick(self.slider,Qt.MouseButton.RightButton,pos=QPoint(300,16))
        self.assertEqual(self.slider.value(),25)
        self.assertFalse(self.slider.isSliderDown())

    def test_native_keyboard_navigation_is_retained(self):
        self.slider.setValue(50)
        QTest.keyClick(self.slider,Qt.Key.Key_Right)
        self.assertEqual(self.slider.value(),51)
        QTest.keyClick(self.slider,Qt.Key.Key_End)
        self.assertEqual(self.slider.value(),100)


class CardSliderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.window=FakeWindow();self.card=LampCard(DEFAULTS[1],self.window)
        self.card.resize(440,640);self.card.show();self.app.processEvents()

    def tearDown(self):
        self.card.close();self.card.deleteLater();self.app.processEvents()

    def test_white_slider_previews_and_ignores_readback_then_sends_once(self):
        slider=self.card.white_brightness
        point=QPoint(slider.width()*3//4,slider.height()//2)
        QTest.mousePress(slider,Qt.MouseButton.LeftButton,pos=point)
        value=slider.value()
        self.assertAlmostEqual(value,75,delta=3)
        self.assertIn(str(value)+' %',slider.caption.text())
        self.card.show_state(dict(power=True,mode='white',brightness=1,temperature=100))
        self.assertEqual(slider.value(),value)
        self.assertEqual(self.window.commands,[])
        QTest.mouseRelease(slider,Qt.MouseButton.LeftButton,pos=point)
        self.assertEqual(len(self.window.commands),1)
        self.assertEqual(self.window.commands[0][1:],('white',{'temperature':20.0,'brightness':value}))

    def test_colour_slider_preserves_hue_and_other_component(self):
        self.card.show_state(dict(power=True,mode='colour',hsv=dict(h=240,s=35,v=80)))
        self.app.processEvents()
        for name,component in (('saturation','s'),('colour_brightness','v')):
            slider=getattr(self.card,name)
            point=QPoint(slider.width()//2,slider.height()//2)
            self.window.commands.clear()
            QTest.mousePress(slider,Qt.MouseButton.LeftButton,pos=point)
            self.assertEqual(self.window.commands,[])
            QTest.mouseRelease(slider,Qt.MouseButton.LeftButton,pos=point)
            self.assertEqual(len(self.window.commands),1)
            _,action,payload=self.window.commands[0]
            self.assertEqual(action,'hsv');self.assertEqual(payload['h'],240)
            self.assertEqual(payload[component],slider.value())
            if component=='s':self.assertEqual(payload['v'],80)
            else:self.assertEqual(payload['s'],self.card.saturation.value())


if __name__=='__main__':unittest.main()

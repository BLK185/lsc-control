"""Render the Windows dialogs with sample data, without using an LSC session."""
import os
import sys
from pathlib import Path
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
from PySide6.QtWidgets import QApplication, QPushButton
from PySide6.QtCore import QEvent
from core import Controller, DEFAULTS
from desktop import Window
from feature_panels import Countdown
from lsc_planning import Planning, TimerEditor
from theme import apply_theme


class PreviewStore:
    def __init__(self):
        self.config = {"mode":"local", "devices":[dict(item) for item in DEFAULTS]}
        self.config["devices"][1].update(name="Lampe RGB")
        for device in self.config["devices"]:
            device["lsc_functions"] = {code:{"id":str(dp), "mode":"rw", "values":{}}
                for dp, code in enumerate(["switch_led","work_mode","bright_value","temp_value","scene_data","countdown"] + (["colour_data"] if device["rgb"] else []),20)}

    def load(self):
        return self.config


app = QApplication([])
apply_theme(app)
store = PreviewStore()
controller = Controller(store,demo=True)
window = Window(controller)
window.timer.stop()
window.complete("refresh",([controller.status(slot) for slot in window.cards],None))
countdown = Countdown(window.cards["a60"])
with patch.object(Planning,"refresh"):
    planning = Planning(controller,"a60")
rows = [{"time":"06:00","dps":{"20":True},"loops":"0111110","status":1,
         "category_status":1,"isAppPush":False,"timerId":1},
        {"time":"07:05","dps":{"20":False},"loops":"0111110","status":1,
         "category_status":1,"isAppPush":True,"timerId":2}]
with patch.object(planning,"refresh") as request:
    for active in (False,True):
        planning.complete([dict(rows[0],status=int(active))],None)
        card = planning.rows_layout.itemAt(0).widget()
        toggle = next(button for button in card.findChildren(QPushButton) if button.property("role")=="toggle")
        toggle.click()
        assert toggle.isChecked() is active
    assert request.call_count==2
planning.complete(rows,None)
app.sendPostedEvents(None,QEvent.Type.DeferredDelete)
editor = TimerEditor(store.config["devices"][1])
assert editor.values() == {"time":"06:00","loops":"0111110","power":True,
                           "enabled":True,"notify":True,"alias":""}
assert all(field.suffix()=="" for field in (countdown.hours,countdown.minutes,countdown.seconds))
for widget, name in ((window,"main"),(countdown,"countdown"),(planning,"planning"),(editor,"editor")):
    widget.show()
    app.processEvents()
    widget.grab().save(str(ROOT / "app" / f"preview-purple-{name}.png"))
    print(name,widget.size().width(),widget.size().height())
editor.reject()
planning.reject()
countdown.reject()
window.quit()

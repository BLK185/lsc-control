"""Quick controls using the same command queue and readback as the main window."""
from PySide6.QtWidgets import QMenu
from lighting import capabilities


def state_label(state):
    if not state or state.get("error"):
        return "État indisponible"
    if state.get("online") is False:
        return "Hors ligne"
    power = "Allumée" if state.get("power") else "Éteinte"
    mode = {"white": "blanc", "colour": "couleur", "scene": "scène"}.get(state.get("mode"))
    return power + (" · " + mode if mode else "")


class TrayMenu(QMenu):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.aboutToShow.connect(self.rebuild)
        self.rebuild()

    def add_command(self, menu, label, slot, action, value):
        item = menu.addAction(label)
        item.triggered.connect(lambda checked=False: self.window.command(slot, action, value))
        return item

    def submenu(self, parent, label):
        menu = QMenu(label, parent)
        parent.addMenu(menu)
        self.submenus.append(menu)
        return menu

    def brightness(self, slot, percent):
        # RGB brightness is HSV V, not the separate white brightness DP.
        state = self.window.device_states.get(slot, {})
        if state.get("error") or state.get("online") is False:
            return
        if state.get("mode") == "colour" and state.get("hsv"):
            hsv = dict(state["hsv"], v=percent)
            self.window.command(slot, "hsv", hsv)
        elif state.get("mode") == "white":
            self.window.command(slot, "brightness", percent)

    def open_panel(self, slot, panel):
        self.window.open_window()
        getattr(self.window.cards[slot], panel)()

    def rebuild(self):
        self.clear()
        for menu in getattr(self, "submenus", []):
            menu.deleteLater()
        self.submenus = []
        self.addAction("Ouvrir LSC Control", self.window.open_window)
        self.addSeparator()
        for device in self.window.controller.devices():
            caps = capabilities(device)
            slot = device["slot"]
            state = self.window.device_states.get(slot, {})
            menu = self.submenu(self, device["name"])
            menu.addAction(state_label(state)).setEnabled(False)
            menu.addSeparator()
            self.add_command(menu, "Allumer", slot, "power", True)
            self.add_command(menu, "Éteindre", slot, "power", False)
            if caps["brightness"] or caps["rgb"]:
                light = self.submenu(menu, "Luminosité")
                known = (not state.get("error") and state.get("online") is not False and
                         (state.get("mode") == "white" or
                          (state.get("mode") == "colour" and bool(state.get("hsv")))))
                light.setEnabled(known)
                for percent in (10, 25, 50, 75, 100):
                    item = light.addAction(f"{percent} %")
                    item.setCheckable(True)
                    item.setChecked(round(state.get("brightness") or 0) == percent)
                    item.triggered.connect(lambda checked=False, s=slot, p=percent: self.brightness(s, p))
            if caps["temperature"]:
                whites = self.submenu(menu, "Blancs · luminosité 100 %")
                for label, temperature in (("Chaud", 0), ("Neutre", 50), ("Froid", 100)):
                    self.add_command(whites, label, slot, "white", {"temperature": temperature, "brightness": 100})
            if device["rgb"]:
                colours = self.submenu(menu, "Couleurs · luminosité 100 %")
                for label, hue in (("Rouge", 0), ("Jaune", 60), ("Vert", 120), ("Cyan", 180), ("Bleu", 240), ("Violet", 280)):
                    self.add_command(colours, label, slot, "hsv", {"h": hue, "s": 100, "v": 100})
            if caps["scenes"]:
                scenes = self.submenu(menu, "Scènes")
                options = state.get("scenes", [])
                scenes.setEnabled(bool(options) and not state.get("error"))
                for scene in options:
                    self.add_command(scenes, scene["name"], slot, "scene", scene["data"])
            menu.addSeparator()
            if caps["countdown"]:
                menu.addAction("Compte à rebours…", lambda checked=False, s=slot: self.open_panel(s, "countdown"))
            if caps["planning"]:
                menu.addAction("Planning partagé…", lambda checked=False, s=slot: self.open_panel(s, "planning"))
        self.addSeparator()
        self.addAction("Tout allumer", lambda: self.window.group(True))
        self.addAction("Tout éteindre", lambda: self.window.group(False))
        self.addAction("Synchroniser", lambda: self.window.refresh(force=True))
        self.addAction("Connexion LSC…", self.window.lsc_login)
        if hasattr(self.window, "mac_integration"):
            self.addAction("Centre de contrôle…", self.window.mac_integration.configure_controls)
        self.addSeparator()
        self.addAction("Quitter", self.window.quit)

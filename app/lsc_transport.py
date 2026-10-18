"""Translate only the bulb functions and encodings observed in its LSC state."""
import colorsys
import json
import re
from core import ControlError, cloud_command, cloud_state, decode_hsv


def lsc_state(detail, functions):
    values = {code:detail["dps"].get(spec["id"]) for code, spec in functions.items()}
    state = cloud_state(values, functions)
    raw = values.get("colour_data_v2", values.get("colour_data"))
    if raw is not None:
        maximum = 255 if isinstance(raw, str) and len(raw) == 14 else 1000
        state["hsv"] = decode_hsv(raw, maximum)
        if state["mode"] == "colour" and state["hsv"]:
            state["brightness"] = state["hsv"]["v"]
    state["online"] = detail.get("isOnline")
    state["scene_data"] = values.get("scene_data_v2",values.get("scene_data"))
    countdown = values.get("countdown",values.get("countdown_1"))
    state["countdown"] = countdown if type(countdown) is int and 0 <= countdown <= 86400 else None
    return state


def lsc_command(functions, dps, action, value):
    def writable(code):
        spec = functions.get(code)
        if not spec or "w" not in spec.get("mode", ""):
            raise ControlError("Cette fonction n'est pas modifiable sur l'ampoule.")
        return spec["id"]
    if action == "countdown":
        code = "countdown" if "countdown" in functions else "countdown_1"
        dp = writable(code)
        limits = functions[code].get("values",{})
        if type(value) is not int or not limits.get("min",0) <= value <= limits.get("max",0):
            raise ControlError("Durée non prise en charge par cette ampoule.")
        return {dp:value}
    if action == "scene":
        from light_features import validate_scene
        code = "scene_data_v2" if "scene_data_v2" in functions else "scene_data"
        value = validate_scene(value, "colour_data" in functions or "colour_data_v2" in functions)
        limit = functions.get(code,{}).get("values",{}).get("maxlen",0)
        if len(value)>limit:
            raise ControlError("Cette scène dépasse la capacité de l'ampoule.")
        return {writable("work_mode"):"scene",writable(code):value}
    if action == "white":
        commands = {}
        for feature, codes in (("temperature", ("temp_value", "temp_value_v2")),
                               ("brightness", ("bright_value", "bright_value_v2"))):
            if any(code in functions for code in codes):
                commands.update(lsc_command(functions, dps, feature, value[feature]))
        if not commands:
            raise ControlError("Cet éclairage n'a pas de réglage blanc.")
        if "work_mode" in functions:
            commands[writable("work_mode")] = "white"
        return commands
    if action == "brightness":
        code = "bright_value_v2" if "bright_value_v2" in functions else "bright_value"
        spec = functions.get(code,{}).get("values",{})
        low,high,step = spec.get("min"),spec.get("max"),spec.get("step",1)
        if type(low) not in (int,float) or type(high) not in (int,float) or high<=0 or step<=0:
            raise ControlError("Plage de luminosité inconnue.")
        raw=round(high*value/100/step)*step
        return {writable(code):max(low,min(high,raw))}
    if action in ("colour", "hsv"):
        code = "colour_data_v2" if "colour_data_v2" in functions else "colour_data"
        dp = writable(code)
        raw = dps.get(dp)
        if action == "colour":
            h, s, v = colorsys.rgb_to_hsv(*(channel / 255 for channel in value))
            hsv = {"h":round(h*360), "s":round(s*1000), "v":round(v*1000)}
        else:
            hsv = {"h":round(value["h"]), "s":round(value["s"]*10), "v":round(value["v"]*10)}
        if isinstance(raw, str) and re.fullmatch(r"[a-fA-F0-9]{12}", raw):
            encoded = "".join(f"{hsv[k]:04x}" for k in ("h", "s", "v"))
        elif isinstance(raw, str) and re.fullmatch(r"[a-fA-F0-9]{14}", raw):
            rgb = colorsys.hsv_to_rgb(hsv['h'] / 360, hsv['s'] / 1000, hsv['v'] / 1000)
            encoded = ''.join(f'{round(c * 255):02x}' for c in rgb)
            encoded += f"{hsv['h']:04x}{round(hsv['s'] * 255 / 1000):02x}{round(hsv['v'] * 255 / 1000):02x}"
        elif isinstance(raw, str) and raw.startswith("{") and decode_hsv(raw):
            encoded = json.dumps(hsv, separators=(",", ":"))
        elif isinstance(raw, dict) and decode_hsv(raw):
            encoded = hsv
        else:
            raise ControlError("Format de couleur LSC non reconnu. Aucune couleur envoyée.")
        result = {dp:encoded}
        if "work_mode" in functions:
            spec = functions['work_mode'].get('values', {})
            modes = spec.get('range', [])
            result[writable("work_mode")] = "color" if "color" in modes and "colour" not in modes else "colour"
        return result
    commands = cloud_command(functions, action, value)
    return {writable(command["code"]):command["value"] for command in commands}

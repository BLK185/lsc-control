"""Validated scene codec for the documented Tuya lighting protocol."""
import re
from core import ControlError

SCENE_NAMES = ("Nuit", "Lecture", "Travail", "Détente", "Douce", "Multicolore", "Colorée", "Arc-en-ciel")


def decode_scene(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]+", value):
        return None
    if not 28 <= len(value) <= 210 or (len(value)-2) % 26:
        return None
    nodes = []
    for start in range(2, len(value), 26):
        block = value[start:start+26]
        interval, duration, mode = (int(block[p:p+2],16) for p in (0,2,4))
        hue, saturation, colour, white, temperature = (int(block[p:p+4],16) for p in (6,10,14,18,22))
        if interval>100 or duration>100 or mode>2 or hue>360 or any(n>1000 for n in (saturation,colour,white,temperature)):
            return None
        nodes.append({"interval":interval,"duration":duration,"mode":mode,"h":hue,
                      "s":saturation,"v":colour,"white":white,"temperature":temperature})
    return {"id":int(value[:2],16), "nodes":nodes, "data":value.lower()}


def validate_scene(value, rgb=True):
    parsed = decode_scene(value)
    if not parsed:
        raise ControlError("Format de scène non reconnu.")
    if not rgb and any(node["v"]>0 for node in parsed["nodes"]):
        raise ControlError("Cette ampoule ne prend en charge que les scènes en lumière blanche.")
    return parsed["data"]


def _node(h=0,s=0,v=0,white=0,temperature=0,mode=0,interval=14,duration=13):
    return f"{interval:02x}{duration:02x}{mode:02x}{h:04x}{s:04x}{v:04x}{white:04x}{temperature:04x}"


def scene_options(rgb, captured=None):
    """Use the last scene received from LSC when available, preserving phone edits."""
    values = [
        "00"+_node(white=200),
        "01"+_node(white=1000,temperature=500),
        "02"+_node(white=1000,temperature=1000),
        "03"+_node(white=500,temperature=0),
    ]
    if rgb:
        values += [
            "04"+_node(h=0,s=1000,v=150,mode=2,interval=30,duration=30)+_node(h=0,s=1000,v=700,mode=2,interval=30,duration=30),
            "05"+"".join(_node(h=h,s=1000,v=1000,mode=2,interval=30,duration=30) for h in (0,120,240)),
            "06"+"".join(_node(h=h,s=900,v=800,mode=2,interval=30,duration=30) for h in (30,180,300)),
            "07"+"".join(_node(h=h,s=1000,v=1000,mode=2,interval=30,duration=30) for h in (0,60,120,180,240,300)),
        ]
    by_id = {decode_scene(value)["id"]:{"id":decode_scene(value)["id"], "name":SCENE_NAMES[decode_scene(value)["id"]],
                                      "data":value,"received":False} for value in values}
    for raw in (captured or {}).values():
        parsed = decode_scene(raw)
        if not parsed or (not rgb and any(node["v"]>0 for node in parsed["nodes"])):
            continue
        number = parsed["id"]
        by_id[number] = {"id":number,"name":SCENE_NAMES[number] if number<len(SCENE_NAMES) else f"Scène {number+1}",
                         "data":parsed["data"],"received":True}
    return list(by_id.values())

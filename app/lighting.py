"""Lighting eligibility and controls derived from each device's declared schema."""
import json

# Tuya Lighting Scenario categories, not product names or user-editable labels.
LIGHTING_CATEGORIES = frozenset({
    "dj", "dsd", "dd", "hcdd", "dc", "td", "xyd", "fwd", "tyd", "tyndj",
    "gyd", "zmqd", "zmkzq", "xdd", "fsd", "mbd", "txd", "sxd", "xkd",
})


def capabilities(device):
    functions = device.get("lsc_functions")
    if functions is None:  # Existing local profiles and isolated demonstration.
        return dict(power=True, brightness=True, temperature=True, white=True,
                    rgb=bool(device.get("rgb")), scenes=True, countdown=True, planning=True)

    def has(*codes):
        return any(code in functions and "w" in functions[code].get("mode", "") for code in codes)

    brightness = has("bright_value", "bright_value_v2")
    temperature = has("temp_value", "temp_value_v2")
    rgb = has("colour_data", "colour_data_v2")
    return dict(power=has("switch_led"), brightness=brightness, temperature=temperature,
                white=brightness or temperature, rgb=rgb,
                scenes=has("scene_data", "scene_data_v2") and has("work_mode"),
                countdown=has("countdown", "countdown_1"), planning=has("switch_led"))


def is_lighting(device, detail, functions):
    category = str(device.get("category") or detail.get("category") or "").lower()
    # HDMI boxes may expose light-like DPs. Check product data and mode schema too.
    metadata = [{key: source.get(key) for key in ("name", "productName", "category", "categoryCode")}
                for source in (device, detail)]
    if "hdmi" in json.dumps([metadata, functions], ensure_ascii=False).lower():
        return False
    if category and category not in LIGHTING_CATEGORIES:
        return False
    caps = capabilities({"lsc_functions": functions})
    return caps["power"] and (category in LIGHTING_CATEGORIES or
                             caps["white"] or caps["rgb"])

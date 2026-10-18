import json
import tempfile
import threading
import unittest
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from core import Controller, ControlError, DEFAULTS, cloud_command, cloud_state, decode_hsv, validate_command, TuyaCloud
from bridge import create_server

class MemoryStore:
    def __init__(self):
        self.config = {"mode": "local", "region": "eu", "devices": [dict(d) for d in DEFAULTS]}
        self.secrets = {}
    def load(self): return self.config
    def secret(self, key): return self.secrets.get(key, "")

class CoreTests(unittest.TestCase):
    def setUp(self):
        self.controller = Controller(MemoryStore(), demo=True)

    def test_slots_independent(self):
        self.controller.command("a65", "power", True)
        self.assertTrue(self.controller.status("a65")["power"])
        self.assertFalse(self.controller.status("a60")["power"])

    def test_cct_rejects_colour_before_any_transport(self):
        with self.assertRaises(ControlError):
            self.controller.command("a65", "colour", [255, 0, 0])

    def test_invalid_values(self):
        for action, value in [("power", 1), ("brightness", -1), ("brightness", True), ("temperature", 101), ("colour", [256, 0, 0]), ("reset", True)]:
            with self.subTest(action=action, value=value), self.assertRaises(ControlError):
                validate_command(action, value, True)

    def test_unknown_slot(self):
        with self.assertRaises(ControlError):
            self.controller.command("other", "power", True)

    def test_cloud_schema_not_guessed(self):
        with self.assertRaises(ControlError):
            cloud_command({}, "power", True)

    def test_cloud_range_and_mode(self):
        functions = {"temp_value_v2": {"values": '{"min":0,"max":1000,"step":1}'}, "work_mode": {}}
        commands = cloud_command(functions, "temperature", 25)
        self.assertEqual(commands, [{"code": "work_mode", "value": "white"}, {"code": "temp_value_v2", "value": 250}])

    def test_cloud_legacy_colour_rejected(self):
        with self.assertRaises(ControlError):
            cloud_command({"colour_data": {}, "work_mode": {}}, "colour", [255, 0, 0])

    def test_cloud_colour_v2(self):
        result = cloud_command({"colour_data_v2": {}, "work_mode": {}}, "colour", [255, 0, 0])
        self.assertEqual(json.loads(result[1]["value"]), {"h": 0, "s": 1000, "v": 1000})

    def test_saturation_and_brightness_are_independent(self):
        state = self.controller.command("a60", "hsv", {"h": 120, "s": 25, "v": 80})
        self.assertEqual(state["hsv"], {"h": 120, "s": 25, "v": 80})
        self.assertEqual(state["brightness"], 80)
        self.assertEqual(state["mode"], "colour")
        self.assertEqual(self.controller.status("a65")["mode"], "white")

    def test_demo_state_copy_cannot_mutate_controller(self):
        state = self.controller.status("a60")
        state["hsv"]["s"] = 3
        self.assertEqual(self.controller.status("a60")["hsv"]["s"], 100)

    def test_invalid_hsv_and_cct_rejected(self):
        for value in ({"h": 361, "s": 50, "v": 50}, {"h": 1, "s": True, "v": 50}, {"h": 1, "s": 50}, {"h": 1, "s": 101, "v": 50}):
            with self.subTest(value=value), self.assertRaises(ControlError):
                self.controller.command("a60", "hsv", value)
        with self.assertRaises(ControlError):
            self.controller.command("a65", "hsv", {"h": 0, "s": 100, "v": 100})

    def test_cloud_hsv_encoding_preserves_saturation(self):
        result = cloud_command({"colour_data_v2": {}, "work_mode": {}}, "hsv", {"h": 240, "s": 35, "v": 72})
        self.assertEqual(json.loads(result[1]["value"]), {"h": 240, "s": 350, "v": 720})

    def test_decode_hsv_and_unknown_values(self):
        self.assertEqual(decode_hsv("00f001f402ee"), {"h": 240, "s": 50, "v": 75})
        self.assertEqual(decode_hsv('{"h":120,"s":1000,"v":800}'), {"h": 120, "s": 100, "v": 80})
        for value in (None, "nonsense", '{"h":361,"s":1000,"v":800}', '{"h":0,"s":true,"v":800}'):
            self.assertIsNone(decode_hsv(value))

    def test_cloud_readback_uses_colour_brightness(self):
        values = {"switch_led": True, "work_mode": "colour", "bright_value_v2": 900,
                  "temp_value_v2": 200, "colour_data_v2": '{"h":240,"s":350,"v":720}'}
        functions = {"bright_value_v2": {"values": '{"max":1000}'}, "temp_value_v2": {"values": '{"max":1000}'}}
        state = cloud_state(values, functions)
        self.assertEqual(state["brightness"], 72)
        self.assertEqual(state["temperature"], 20)
        self.assertEqual(state["hsv"]["s"], 35)

    def test_cloud_timeout_and_token(self):
        class Response:
            def __init__(self, data): self.data = data
            def raise_for_status(self): pass
            def json(self): return self.data
        class Session:
            def __init__(self): self.calls = []
            def request(self, method, url, **kw):
                self.calls.append((method, url, kw))
                if "token?" in url:
                    return Response({"success": True, "result": {"access_token": "test-token", "expire_time": 7200}})
                return Response({"success": True, "result": [{"code": "switch_led", "value": True}]})
        session = Session()
        cloud = TuyaCloud("eu", "test-id", "test-secret", session)
        self.assertEqual(cloud.status("a/b")["switch_led"], True)
        cloud.status("a/b")
        self.assertEqual(len(session.calls), 3)
        self.assertIn("a%2Fb", session.calls[1][1])
        self.assertEqual(session.calls[1][2]["timeout"], (5, 12))
        self.assertEqual(session.calls[1][2]["headers"]["access_token"], "test-token")

class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.server = create_server(Controller(MemoryStore(), demo=True), "test-token", 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = "http://127.0.0.1:" + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def fetch(self, path, data=None, token="test-token", origin=None):
        headers = {"Authorization": "Bearer " + token}
        if origin: headers["Origin"] = origin
        request = Request(self.base + path, data=data, headers=headers)
        with urlopen(request, timeout=3) as response:
            return json.load(response)

    def test_command_and_readback(self):
        payload = json.dumps({"slot": "a65", "action": "power", "value": True}).encode()
        self.assertTrue(self.fetch("/command", payload)["power"])
        self.assertTrue(self.fetch("/status/a65")["power"])

    def test_authentication_and_browser_origin_rejected(self):
        for token, origin in [("wrong", None), ("test-token", "https://example.org")]:
            with self.assertRaises(HTTPError) as error:
                self.fetch("/status/a65", token=token, origin=origin)
            self.assertEqual(error.exception.code, 401)

    def test_invalid_payload(self):
        with self.assertRaises(HTTPError) as error:
            self.fetch("/command", b"not-json")
        self.assertEqual(error.exception.code, 400)

    def test_unsupported_cct_colour(self):
        payload = json.dumps({"slot": "a65", "action": "colour", "value": [255, 0, 0]}).encode()
        with self.assertRaises(HTTPError) as error:
            self.fetch("/command", payload)
        self.assertEqual(error.exception.code, 409)


class LocalTransportTests(unittest.TestCase):
    def bulb(self, dps):
        import tinytuya
        bulb = tinytuya.BulbDevice("test-id", "192.168.1.200", "1234567890123456", version=3.3)
        bulb.detect_bulb({"dps": dps})
        bulb.status = MagicMock(side_effect=lambda: {"dps": dict(dps)})
        bulb.close = MagicMock()
        def write(value, switch, nowait=False):
            dps[str(switch)] = value
            return {"dps": dict(dps)}
        bulb.set_status = MagicMock(side_effect=write)
        return bulb

    def controller(self):
        store = MemoryStore()
        store.config["devices"][0]["device_id"] = "test-id"
        return Controller(store)

    def test_type_b_uses_power_dp20_and_reads_back(self):
        controller = self.controller()
        bulb = self.bulb({"20": False, "21": "white", "22": 700, "23": 450, "24": "000003e803e8"})
        with patch.object(controller, "_local", return_value=bulb):
            result = controller.command("a65", "power", True)
        self.assertTrue(result["power"])
        bulb.set_status.assert_called_once_with(True, "20", nowait=False)
        self.assertEqual(result["brightness"], 70)
        self.assertEqual(result["temperature"], 45)
        self.assertEqual(bulb.close.call_count, 2)

    def test_cct_type_c_uses_dp1(self):
        controller = self.controller()
        bulb = self.bulb({"1": True, "2": 128, "3": 0})
        with patch.object(controller, "_local", return_value=bulb):
            result = controller.command("a65", "power", False)
        self.assertFalse(result["power"])
        bulb.set_status.assert_called_once_with(False, "1", nowait=False)

    def test_unknown_schema_sends_nothing(self):
        controller = self.controller()
        bulb = self.bulb({"99": False})
        with patch.object(controller, "_local", return_value=bulb), self.assertRaises(ControlError):
            controller.command("a65", "power", True)
        bulb.set_status.assert_not_called()

    def test_external_changes_are_read_back_in_colour_mode(self):
        controller = self.controller()
        dps = {"20": True, "21": "colour", "22": 900, "23": 450, "24": "00f001f402ee"}
        bulb = self.bulb(dps)
        with patch.object(controller, "_local", return_value=bulb):
            first = controller.status("a65")
            dps["24"] = "007803e801f4"
            second = controller.status("a65")
        self.assertEqual(first["brightness"], 75)
        self.assertEqual(first["hsv"]["s"], 50)
        self.assertEqual(second["brightness"], 50)
        self.assertEqual(second["hsv"]["h"], 120)
        bulb.set_status.assert_not_called()

if __name__ == "__main__":
    unittest.main()

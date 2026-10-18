import unittest
from core import ControlError
from lsc_account import schema_functions
from lsc_transport import lsc_command, lsc_state

SCHEMA = [
    {"code":"switch_led","id":20,"mode":"rw","property":{"type":"bool"}},
    {"code":"work_mode","id":21,"mode":"rw","property":{"type":"enum"}},
    {"code":"bright_value","id":22,"mode":"rw","property":{"min":10,"max":1000,"step":1}},
    {"code":"temp_value","id":23,"mode":"rw","property":{"min":0,"max":1000,"step":1}},
    {"code":"colour_data","id":24,"mode":"rw","property":{"type":"string"}},
]


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.functions = schema_functions(SCHEMA)
        self.dps = {"20":True,"21":"colour","22":1000,"23":200,"24":"007800fa0320"}

    def test_rgb_readback_uses_observed_1000_scale_even_with_legacy_code_name(self):
        state = lsc_state({"dps":self.dps,"isOnline":True}, self.functions)
        self.assertEqual(state["hsv"], {"h":120,"s":25,"v":80})
        self.assertEqual(state["brightness"],80)

    def test_rgb_command_preserves_actual_hex_encoding(self):
        result = lsc_command(self.functions,self.dps,"hsv",{"h":240,"s":50,"v":75})
        self.assertEqual(result, {"21":"colour","24":"00f001f402ee"})

    def test_rgb_command_rejects_unknown_encoding(self):
        with self.assertRaises(ControlError):
            lsc_command(self.functions,{"24":"unknown"},"hsv",{"h":0,"s":100,"v":100})

    def test_white_switches_mode_and_maps_the_declared_dp(self):
        self.assertEqual(lsc_command(self.functions,self.dps,"temperature",25),
                         {"21":"white","23":250})

    def test_read_only_schema_cannot_send_power(self):
        self.functions["switch_led"]["mode"] = "ro"
        with self.assertRaises(ControlError):
            lsc_command(self.functions,self.dps,"power",False)

    def test_cct_schema_has_no_colour_function(self):
        del self.functions["colour_data"]
        with self.assertRaises(ControlError):
            lsc_command(self.functions,self.dps,"hsv",{"h":0,"s":100,"v":100})

    def test_offline_flag_survives_status_normalization(self):
        self.assertFalse(lsc_state({"dps":self.dps,"isOnline":False},self.functions)["online"])


if __name__ == "__main__": unittest.main()

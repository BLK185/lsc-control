import unittest
from core import ControlError,validate_command
from light_features import scene_options,decode_scene
from lsc_transport import lsc_command,lsc_state
from test_lsc_transport import SCHEMA
from lsc_account import schema_functions

class FeaturesTests(unittest.TestCase):
    def setUp(self):
        self.functions=schema_functions(SCHEMA+[
            {'id':25,'code':'scene_data','mode':'rw','property':{'type':'string','maxlen':255}},
            {'id':26,'code':'countdown','mode':'rw','property':{'min':0,'max':86400,'step':1}}])

    def test_presets_obey_protocol_and_white_bulb_limits(self):
        self.assertEqual(len(scene_options(True)),8)
        for scene in scene_options(False):
            validate_command('scene',scene['data'],False)
            self.assertTrue(all(n['v']==0 for n in decode_scene(scene['data'])['nodes']))
        with self.assertRaises(ControlError):validate_command('scene',scene_options(True)[4]['data'],False)

    def test_actual_mobile_night_scene_matches_format(self):
        value='000e0d0000000000000000c80000'
        self.assertEqual(decode_scene(value)['nodes'][0]['white'],200)
        self.assertEqual(scene_options(False)[0]['data'],value)

    def test_phone_scene_edits_override_suggested_variant(self):
        edited='000e0d0000000000000000640000'
        scene=scene_options(True,{'0':edited})[0]
        self.assertEqual(scene['data'],edited)
        self.assertTrue(scene['received'])

    def test_bad_scene_data_is_never_sent(self):
        for value in ('00','00'+'ff'*13,'00'+'00'*14,'../../'):
            with self.subTest(value=value),self.assertRaises(ControlError):
                validate_command('scene',value,True)

    def test_scene_sets_mode_and_scene_in_one_packet(self):
        raw=scene_options(True)[0]['data']
        self.assertEqual(lsc_command(self.functions,{},'scene',raw),{'21':'scene','25':raw})

    def test_countdown_cancel_does_not_change_power(self):
        self.assertEqual(lsc_command(self.functions,{},'countdown',0),{'26':0})

    def test_countdown_schema_limit_is_enforced(self):
        for bad in (-1,86401,True,'60'):
            with self.subTest(value=bad),self.assertRaises(ControlError):validate_command('countdown',bad,True)
        self.functions['countdown']['values']['max']=60
        with self.assertRaises(ControlError):lsc_command(self.functions,{},'countdown',61)

    def test_white_command_is_atomic_and_percentages_match_mobile(self):
        result=lsc_command(self.functions,{},'white',{'temperature':25,'brightness':25})
        self.assertEqual(result,{'21':'white','23':250,'22':250})

    def test_readback_preserves_countdown_and_scene(self):
        raw=scene_options(True)[0]['data']
        result=lsc_state({'dps':{'20':True,'21':'scene','25':raw,'26':600}},self.functions)
        self.assertEqual(result['countdown'],600)
        self.assertEqual(result['scene_data'],raw)

if __name__=='__main__':unittest.main()

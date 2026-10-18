"""Account catalog and command targeting regressions, using fictitious devices only."""
import copy
import json
import os
import time
import tempfile
import unittest
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication, QPushButton
from PySide6.QtTest import QTest
from core import Controller, ControlError, DEFAULTS, Store as FileStore
from desktop import Window
from lighting import capabilities, is_lighting
from lsc_account import LSCAccount
from lsc_transport import lsc_command, lsc_state
from test_lsc_account import Store


def functions(rgb=False, temperature=True, brightness=True):
    data = {'switch_led': {'id':'20', 'mode':'rw', 'values':{}}}
    for code, dp in [('bright_value', '22')] * brightness + [('temp_value', '23')] * temperature:
        data[code] = dict(id=dp, mode='rw', values=dict(min=0, max=1000, step=1))
    if rgb:
        data['colour_data'] = dict(id='24', mode='rw', values={})
    return data


def detail(f, **values):
    return dict(schema=[dict(code=code, id=int(spec['id']), mode=spec['mode'], property=spec['values'])
                        for code, spec in f.items()], **values)


def device(number, category='dj', **values):
    return dict(devId=f'fictional-light-{number}', name=f'Lampe {number}', category=category, _home_id=42, **values)


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.store = Store()
        self.store.config = dict(mode='lsc', devices=[])
        self.account = LSCAccount(self.store, restore=False)

    def sync(self, devices, details=None, full=True):
        details = details or {d['devId']:detail(functions()) for d in devices}
        def read(api, data, **kwargs):
            result = details[data['devId']]
            if isinstance(result, Exception):
                raise result
            return result
        with patch.object(self.account, 'devices', return_value=devices), patch.object(self.account, 'request', side_effect=read):
            self.account.prepare_bulbs(refresh_schema=full)
        return self.store.config['devices']

    def test_any_number_and_duplicate_models_are_accepted(self):
        for count in (0, 1, 4):
            with self.subTest(count=count):
                lights = self.sync([device(i) for i in range(count)])
                self.assertEqual(len(lights), count)
                self.assertEqual(len({d['slot'] for d in lights}), count)

    def test_add_remove_rename_preserves_identity_local_profile_and_key(self):
        first = self.sync([device(1)])[0]
        first.update(ip='192.168.10.15', lsc_local_available=True, scene_profiles={'0':'scene'})
        slot = first['slot']
        self.store.secrets['local:'+slot] = 'fixture-local-key'
        renamed = device(1); renamed['name'] = 'Bureau'
        lights = self.sync([device(2), renamed])
        retained = lights[1]
        self.assertEqual((retained['slot'], retained['name'], retained['ip']), (slot, 'Bureau', '192.168.10.15'))
        self.assertEqual(retained['scene_profiles'], {'0':'scene'})
        self.assertEqual(self.store.secrets['local:'+slot], 'fixture-local-key')
        self.assertEqual(self.sync([renamed])[0]['slot'], slot)

    def test_old_a65_slot_survives_migration(self):
        self.store.config['devices'] = [dict(DEFAULTS[0], device_id=device(1)['devId'])]
        self.assertEqual(self.sync([device(1)])[0]['slot'], 'a65')

    def test_hdmi_socket_camera_and_sensor_are_excluded(self):
        devices = [device(1), device(2, 'cz'), device(3, 'sp'), device(4, 'hps'), device(5)]
        devices[-1]['productName'] = 'HDMI sync box'
        self.assertEqual(len(self.sync(devices)), 1)

    def test_hdmi_schema_modes_are_excluded_even_if_renamed(self):
        f = functions(); f['work_mode'] = dict(id='21', mode='rw', values={'range':['white','hdmi']})
        self.assertFalse(is_lighting(device(1), {}, f))

    def test_uncategorized_light_requires_a_strong_lighting_schema(self):
        self.assertTrue(is_lighting(device(1, ''), {}, functions()))
        self.assertFalse(is_lighting(device(1, ''), {}, functions(temperature=False, brightness=False)))

    def test_duplicate_devices_in_multiple_homes_do_not_duplicate_cards(self):
        self.assertEqual(len(self.sync([device(1), device(1)])), 1)

    def test_inventory_failure_preserves_catalog(self):
        self.sync([device(1)])
        before = copy.deepcopy(self.store.config)
        with patch.object(self.account, 'devices', side_effect=ControlError('Network')):
            with self.assertRaises(ControlError): self.account.prepare_bulbs()
        self.assertEqual(self.store.config, before)

    def test_transient_detail_error_keeps_known_light(self):
        self.sync([device(1)])
        lights = self.sync([device(1), device(2)], {device(i)['devId']:ControlError('Network') for i in (1,2)})
        self.assertEqual(len(lights), 1)

    def test_malformed_detail_keeps_previous_known_light(self):
        self.sync([device(1)])
        self.assertEqual(len(self.sync([device(1)], {device(1)['devId']:None})), 1)

    def test_fresh_profile_does_not_invent_devices(self):
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory, patch('core.HOME', Path(directory)):
            store = FileStore()
            self.assertEqual(Controller(store).devices(), [])
            self.assertEqual(len(Controller(store, demo=True).devices()), 2)

    def test_lightweight_sync_reuses_schema_and_updates_name(self):
        self.sync([device(1)])
        renamed = device(1); renamed['name'] = 'Salon'
        with patch.object(self.account, 'devices', return_value=[renamed]), patch.object(self.account, 'request') as request:
            self.account.prepare_bulbs(refresh_schema=False)
        request.assert_not_called()
        self.assertEqual(self.store.config['devices'][0]['name'], 'Salon')

    def test_local_keys_never_enter_settings(self):
        self.sync([device(1)], {device(1)['devId']:detail(functions(), localKey='fixture-private-key')})
        self.assertNotIn('fixture-private-key', json.dumps(self.store.config))
        slot = self.store.config['devices'][0]['slot']
        self.assertEqual(self.store.secrets['local:'+slot], 'fixture-private-key')

    def test_automatic_sync_is_throttled_and_manual_sync_forces_schema(self):
        controller = Controller(self.store)
        account = unittest.mock.MagicMock()
        account.connected = True
        with patch('lsc_account.LSCAccount', return_value=account):
            controller.synchronize_lights()
            controller.synchronize_lights()
            account.prepare_bulbs.assert_called_once_with(refresh_schema=True)
            controller.inventory_checked -= 31
            controller.synchronize_lights()
            self.assertEqual(account.prepare_bulbs.call_args.kwargs, {'refresh_schema':False})
            controller.synchronize_lights(force=True)
            self.assertEqual(account.prepare_bulbs.call_args.kwargs, {'refresh_schema':True})

    def test_capabilities_and_commands_for_dimmable_and_rgb_only_lights(self):
        dim = functions(temperature=False)
        self.assertFalse(capabilities({'lsc_functions':dim})['temperature'])
        self.assertEqual(lsc_command(dim, {}, 'white', dict(brightness=30,temperature=10)), {'22':300})
        rgb = functions(rgb=True, temperature=False, brightness=False)
        self.assertFalse(capabilities({'lsc_functions':rgb})['white'])
        result = lsc_command(rgb, {'24':'000003e803e8'}, 'hsv', dict(h=120,s=50,v=75))
        self.assertEqual(result, {'24':'007801f402ee'})
        self.assertEqual(lsc_state({'dps':{'20':True,'24':result['24']}}, rgb)['mode'], 'colour')

    def test_legacy_14_character_rgb_encoding_roundtrips(self):
        f = functions(rgb=True, temperature=False, brightness=False)
        result = lsc_command(f, {'24':'ff00000000ffff'}, 'hsv', dict(h=120,s=100,v=50))
        state = lsc_state({'dps':{'20':True,**result}}, f)
        self.assertEqual(state['hsv'], dict(h=120,s=100,v=50))


class WindowCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.store = Store()
        self.store.config = dict(mode='local', devices=[dict(d) for d in DEFAULTS] + [dict(DEFAULTS[0], slot='third',name='Troisième')])
        self.controller = Controller(self.store, demo=True)
        with patch('desktop.QTimer.singleShot'):
            self.window = Window(self.controller)
        self.window.timer.stop()

    def tearDown(self):
        self.window.executor.shutdown(wait=True)
        self.app.processEvents()
        self.window.tray.hide()
        self.window.exiting = True
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def drain(self):
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            self.app.processEvents()
            QTest.qWait(5)
            if not self.window.busy and not self.window.pending_commands:
                self.app.processEvents()
                QTest.qWait(5)
                if not self.window.busy: return
        self.fail('Command queue did not drain')

    def test_all_on_and_off_reach_each_device_once(self):
        original = self.controller.command
        for power in (True, False):
            with patch.object(self.controller, 'command', wraps=original) as command:
                self.window.group(power)
                self.drain()
            self.assertEqual(command.call_args_list, [unittest.mock.call(slot,'power',power) for slot in ('a65','a60','third')])
            self.assertTrue(all(self.controller.status(d['slot'])['power'] is power for d in self.controller.devices()))

    def test_group_during_read_preserves_each_target(self):
        self.window.busy = True
        self.window.group(True)
        # The old bug captured slot from the LAST returned state in this completion.
        self.window.complete('refresh', ([self.controller.status('third')],None))
        self.drain()
        self.assertTrue(all(self.controller.status(d['slot'])['power'] for d in self.controller.devices()))

    def test_failure_of_one_target_does_not_drop_next_commands(self):
        calls = []
        def command(slot,action,value):
            calls.append(slot)
            if slot == 'a65': raise ControlError('Offline')
            return dict(slot=slot,power=value)
        with patch.object(self.controller,'command',side_effect=command):
            self.window.group(True)
            self.drain()
        self.assertEqual(calls, ['a65','a60','third'])

    def test_reconcile_removes_adds_and_renames_without_commands(self):
        with patch.object(self.controller,'command') as command:
            self.window.reconcile_cards([dict(DEFAULTS[1],name='Salon'),dict(DEFAULTS[0],slot='new',name='Nouvelle')])
        command.assert_not_called()
        self.assertEqual(set(self.window.cards), {'a60','new'})
        self.assertEqual(self.window.cards['a60'].title(), 'Salon')
        self.assertFalse(any('avancé' in b.text() for b in self.window.findChildren(QPushButton)))

    def test_background_refresh_discovers_new_device_without_command(self):
        def sync(force=False):
            self.store.config['devices'].append(dict(DEFAULTS[0],slot='added',name='Nouvelle lampe'))
        with patch.object(self.controller,'synchronize_lights',side_effect=sync), patch.object(self.controller,'command') as command:
            self.window.refresh(observe=True)
            self.drain()
        command.assert_not_called()
        self.assertIn('added', self.window.cards)
        self.assertIn('added', self.window.device_states)

    def test_rgb_only_card_hides_white_scene_and_countdown(self):
        self.window.reconcile_cards([dict(slot='only', name='Ruban', rgb=True, lsc_functions=functions(True,False,False))])
        card = self.window.cards['only']
        self.assertEqual(card.tabs.count(), 1)
        self.assertEqual(card.tabs.tabText(0), 'Couleur')
        self.assertTrue(card.white.isHidden())
        self.assertTrue(card.scene_panel.isHidden())
        card.show_state(dict(power=True, mode='colour',hsv=dict(h=120,s=50,v=80)))
        self.assertEqual(card.tabs.currentIndex(), 0)
        countdown = next(b for b in card.findChildren(QPushButton) if b.text() == 'Compte à rebours')
        self.assertTrue(countdown.isHidden())

    def test_empty_account_shows_no_preconfigured_bulbs(self):
        self.window.reconcile_cards([])
        self.assertEqual(self.window.cards,{})
        self.assertFalse(self.window.empty.isHidden())


if __name__ == '__main__': unittest.main()

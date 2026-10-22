"""Latency regressions: bounded read work, connection reuse, verified caches."""
import copy
import json
import os
import threading
import time
import unittest
from unittest.mock import MagicMock, patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from core import Controller, ControlError, DEFAULTS, InventoryYield
from desktop import Window
from lsc_account import LSCAccount
from test_lsc_account import Store
from test_lsc_transport import SCHEMA
from lsc_account import schema_functions


class TransportLatencyTests(unittest.TestCase):
    def setUp(self):
        self.store = Store()
        self.store.config = {'mode':'lsc','devices':[dict(DEFAULTS[1],device_id='fixture',lsc_home_id=42,
            lsc_functions=schema_functions(SCHEMA))]}
        self.controller = Controller(self.store)
        self.item = self.store.config['devices'][0]
        self.detail = {'dps':{'20':False,'21':'white','22':500,'23':200,'24':'000003e803e8'},'isOnline':True}

    def test_recent_verified_detail_removes_redundant_read_but_write_is_confirmed(self):
        self.controller._lsc_state(self.item,self.detail,'lsc')
        account=MagicMock()
        account.detail.return_value=dict(self.detail,dps=dict(self.detail['dps'],**{'20':True}))
        with patch.object(self.controller,'_account',return_value=account),patch.object(self.controller,'_lsc_local',return_value=None):
            result=self.controller.command('a60','power',True)
        account.publish.assert_called_once_with(self.item,{'20':True})
        account.detail.assert_called_once_with(self.item)
        self.assertTrue(result['power'])

    def test_publish_ack_cannot_be_mistaken_for_verified_power(self):
        self.controller._lsc_state(self.item,self.detail,'lsc')
        account=MagicMock()
        account.detail.side_effect=ControlError('readback unavailable')
        with patch.object(self.controller,'_account',return_value=account),patch.object(self.controller,'_lsc_local',return_value=None):
            with self.assertRaises(ControlError):self.controller.command('a60','power',True)
        self.assertFalse(self.controller.recent_status('a60')['power'])

    def test_cache_expires_and_cannot_follow_reused_slot(self):
        self.controller._lsc_state(self.item,self.detail,'lsc')
        cached=self.controller.recent_status('a60')
        cached['power']=True
        self.assertFalse(self.controller.recent_status('a60')['power'])
        self.assertIsNone(self.controller.recent_status('a60',max_age=-1))
        self.store.config['devices'][0]['device_id']='different-fixture'
        self.assertIsNone(self.controller.recent_status('a60'))
        self.assertIsNone(self.controller._recent_detail(self.store.config['devices'][0]))

    def test_local_command_reuses_recent_raw_encoding_and_confirms_only_once(self):
        self.controller._lsc_state(self.item,self.detail,'lsc-local')
        with patch.object(self.controller,'_lsc_local',return_value=self.detail) as local,patch.object(self.controller,'_account') as account:
            self.controller.command('a60','power',True)
        local.assert_called_once_with(self.item,{'20':True})
        account.assert_not_called()

    def test_account_connection_is_reused_and_invalidated_when_session_changes(self):
        self.store.secrets['lsc_session:eu']=json.dumps({'sid':'synthetic-one','ecode':'fixture'})
        with patch('lsc_account.LSCAccount') as factory:
            first=MagicMock();second=MagicMock();factory.side_effect=[first,second]
            self.assertIs(self.controller._account(self.store.config),first)
            self.assertIs(self.controller._account(self.store.config),first)
            self.store.secrets['lsc_session:eu']=json.dumps({'sid':'synthetic-two','ecode':'fixture'})
            self.assertIs(self.controller._account(self.store.config),second)
        self.assertEqual(factory.call_count,2)
        first.close.assert_called_once()

    def test_inventory_yields_before_next_network_request(self):
        account=LSCAccount(self.store,restore=False)
        account.cancel=lambda:True
        with patch.object(account,'_start') as native:
            with self.assertRaises(InventoryYield):account.request('tuya.m.location.list')
        native.assert_not_called()


class ReadPriorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.store=Store()
        self.store.config={'mode':'local','devices':[dict(device) for device in DEFAULTS]}
        self.controller=Controller(self.store,demo=True)
        with patch('desktop.QTimer.singleShot'):self.window=Window(self.controller)
        self.window.timer.stop()

    def tearDown(self):
        self.window.exiting=True
        self.window.executor.shutdown(wait=True)
        self.window.discovery_executor.shutdown(wait=True)
        self.window.tray.hide();self.window.close();self.window.deleteLater()
        self.app.processEvents()

    def drain(self):
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            self.app.processEvents();QTest.qWait(5)
            if not self.window.busy and not self.window.pending_commands:return
        self.fail('Work did not complete')

    def test_command_runs_after_current_read_without_waiting_for_other_lamps(self):
        started=threading.Event();release=threading.Event();order=[]
        original_status=self.controller.status
        original_command=self.controller.command
        def status(slot):
            order.append(('read',slot))
            if len(order)==1:started.set();release.wait(2)
            return original_status(slot)
        def command(*args):
            order.append(('command',args[0]))
            return original_command(*args)
        with patch.object(self.controller,'status',side_effect=status),patch.object(self.controller,'command',side_effect=command):
            self.window.refresh(observe=True)
            self.assertTrue(started.wait(2))
            self.window.command('a60','power',True)
            release.set();self.drain()
        self.assertEqual(order[:2],[('read','a65'),('command','a60')])

    def test_local_discovery_does_not_take_the_command_worker(self):
        self.controller.demo=False
        release=threading.Event();started=threading.Event()
        def scan():started.set();release.wait(2);return []
        try:
            with patch.object(self.controller,'scan',side_effect=scan):
                self.window.start_local_discovery(force=True)
                self.assertTrue(started.wait(2))
                self.assertFalse(self.window.busy)
                with patch.object(self.controller,'command',return_value={'slot':'a60','power':True}) as command:
                    self.window.command('a60','power',True)
                    self.drain()
                    command.assert_called_once()
        finally:release.set()


if __name__=='__main__':unittest.main()

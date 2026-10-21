"""Control Center capability boundaries with fake lights, never a real account."""
import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

from control_center import create_server, ControlsService, TOKEN_NAME
from core import Controller, DEFAULTS, ControlError

TOKEN = "synthetic_controls_capability_for_tests_only"


class Store:
    def __init__(self):
        self.secrets = {}
    def load(self):
        return {"mode": "local", "devices": [dict(device, device_id="private-device-id",
                lsc_functions={"secret": "private-schema"}) for device in DEFAULTS]}
    def secret(self, key): return self.secrets.get(key, "")
    def set_secret(self, key, value): self.secrets[key] = value


class ControlsTests(unittest.TestCase):
    def setUp(self):
        self.controller = Controller(Store(), demo=True)
        self.changes = []
        self.server = create_server(self.controller, TOKEN, 0, lambda: self.changes.append(True))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = "http://127.0.0.1:" + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def fetch(self, path, data=None, token=TOKEN, **headers):
        headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json", **headers}
        payload = json.dumps(data).encode() if data is not None else None
        with urlopen(Request(self.base + path, data=payload, headers=headers), timeout=3) as response:
            return json.load(response)

    def test_inventory_exposes_only_slot_and_name(self):
        result = self.fetch('/lights')
        self.assertEqual(result, {"lights": [{"id": device['slot'], "name": device['name']} for device in DEFAULTS]})
        self.assertNotIn('private-', json.dumps(result))

    def test_bad_capability_browser_origin_and_forged_host_are_rejected(self):
        for headers in ({'token':'wrong'}, {'Origin':'https://example.com'},
                        {'Referer':'http://example.com/'}, {'Host':'example.com'}):
            with self.subTest(headers=headers), self.assertRaises(HTTPError) as error:
                self.fetch('/lights', **headers)
            self.assertEqual(error.exception.code, 401)

    def test_individual_and_group_commands_are_read_back(self):
        self.assertEqual(self.fetch('/power', {'id':'a60','value':True}), {'power':True})
        self.assertEqual(self.fetch('/power/a60'), {'power':True})
        self.assertEqual(self.fetch('/power', {'id':'all','value':False}), {'power':False})
        self.assertEqual([self.controller.status(device['slot'])['power'] for device in DEFAULTS], [False,False])
        self.assertEqual(len(self.changes), 2)

    def test_groups_read_every_member_and_do_not_hide_later_errors(self):
        with patch.object(self.controller,'status',side_effect=[{'power':False},ControlError('offline')]) as status:
            with self.assertRaises(HTTPError) as error:
                self.fetch('/power/all')
        self.assertEqual(error.exception.code,409)
        self.assertEqual(status.call_count,2)

    def test_group_failure_still_attempts_remaining_lights(self):
        with patch.object(self.controller,'command',side_effect=[ControlError('offline'),{'power':True}]) as command:
            with self.assertRaises(HTTPError) as error:
                self.fetch('/power', {'id':'all','value':True})
        self.assertEqual(error.exception.code,409)
        self.assertEqual(command.call_count,2)

    def test_other_commands_and_session_routes_are_not_available(self):
        for path, data in (('/session',None),('/status/a60',None),('/command',{'slot':'a60','action':'countdown','value':300})):
            with self.subTest(path=path), self.assertRaises(HTTPError) as error:
                self.fetch(path,data)
            self.assertEqual(error.exception.code,404)

    def test_non_boolean_unknown_extra_fields_and_form_content_are_rejected(self):
        for data in ({'id':'a60','value':1},{'id':'a60','value':'true'},
                     {'id':'a60','value':True,'action':'scene'}, ['a60',True]):
            with self.subTest(data=data),self.assertRaises(HTTPError) as error:
                self.fetch('/power',data)
            self.assertEqual(error.exception.code,400)
        with self.assertRaises(HTTPError) as error:
            self.fetch('/power',{'id':'a60','value':True},**{'Content-Type':'text/plain'})
        self.assertEqual(error.exception.code,400)
        self.assertEqual(self.changes,[])

    def test_removed_or_invalid_slot_never_changes_another_light(self):
        for slot in ('missing','../all','all?x=1'):
            with self.subTest(slot=slot),self.assertRaises(HTTPError):
                self.fetch('/power',{'id':slot,'value':True})
        self.assertFalse(self.controller.status('a60')['power'])


class CapabilityLifecycleTests(unittest.TestCase):
    def test_capability_survives_restart_and_rotation_revokes_old_access(self):
        store=Store()
        controller=Controller(store,demo=True)
        def factory(controller,token,**kwargs):
            return create_server(controller,token,0,**kwargs)
        with patch('control_center.create_server',side_effect=factory):
            service=ControlsService(controller)
            try:
                first=service.enable()
                self.assertEqual(store.secret(TOKEN_NAME),first)
                service.close()
                service.restore()
                self.assertEqual(service.token,first)
                second=service.enable(rotate=True)
                self.assertNotEqual(first,second)
                base='http://127.0.0.1:'+str(service.server.server_port)
                with self.assertRaises(HTTPError) as error:
                    urlopen(Request(base+'/lights',headers={'Authorization':'Bearer '+first}),timeout=3)
                self.assertEqual(error.exception.code,401)
            finally:
                service.close()


if __name__=='__main__':unittest.main()

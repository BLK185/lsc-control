"""First-run setup security and QR UI flow, with synthetic artifacts only."""
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from connection_setup import Asar, DEFAULT_FIELDS, download, identity_from_source, prepare, verify_file
from core import ControlError
from lsc_account import connection_ready, portable_identity_path, runtime_root
from lsc_login import LSCLogin


def fixture_source(**overrides):
    fields={name:'value' for name in DEFAULT_FIELDS}
    fields.update(clientId=None,**overrides)
    lines=[name+': '+('APPKEY' if value is None else json.dumps(value))+',' for name,value in fields.items()]
    return 'export const APPKEY="synthetic-client";\nexport const APPSECRET="synthetic-secret";\nexport const POST_DEFAULTPARAMS={\n'+'\n'.join(lines)+'\n};'


def write_asar(path,entries):
    content=json.dumps({'files':entries}).encode()
    # Chromium Pickle: outer size, inner buffer size, payload size, string length.
    path.write_bytes(struct.pack('<4I',4,8+len(content),4+len(content),len(content))+content+b'hello')


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def artifact(self,data=b'official'):
        return dict(url='https://downloads.action.com/test.exe',size=len(data),sha256=hashlib.sha256(data).hexdigest())

    def test_own_installation_identity_is_generated_without_session_fields(self):
        first=identity_from_source(fixture_source());second=identity_from_source(fixture_source())
        self.assertNotEqual(first['defaults']['deviceId'],second['defaults']['deviceId'])
        self.assertEqual(first['defaults']['clientId'],first['APPKEY'])
        self.assertEqual(set(first),{'APPKEY','APPSECRET','defaults'})
        self.assertFalse({'sid','ecode','localKey'} & set(first['defaults']))

    def test_javascript_is_never_executed_and_unknown_defaults_are_rejected(self):
        for source in (fixture_source() .replace('APPKEY,','dangerousCall(),'),
                       fixture_source().replace('appVersion:', 'sid:'),
                       fixture_source().replace('"synthetic-secret"','process.env.SECRET')):
            with self.subTest(),self.assertRaises((ValueError,SyntaxError)):
                identity_from_source(source)

    def test_archive_traversal_links_and_unpacked_members_are_rejected(self):
        for entries in ({'..':{'files':{}}},{'x/y':{'size':5,'offset':'0'}},
                        {'x':{'link':'../secret'}},{'x':{'unpacked':True}}):
            path=self.root/'app.asar';write_asar(path,entries)
            with self.subTest(),self.assertRaises(ValueError): Asar(path)

    def test_archive_member_cannot_read_outside_payload(self):
        path=self.root/'app.asar';write_asar(path,{'x':{'size':50,'offset':'0'}})
        archive=Asar(path)
        with self.assertRaises(ValueError):archive.read('x')

    def test_only_node_modules_are_extracted(self):
        path=self.root/'app.asar';write_asar(path,{'node_modules':{'files':{'x.js':{'size':5,'offset':'0'}}},'account.json':{'size':5,'offset':'0'}})
        archive=Asar(path);archive.extract_modules(self.root/'out')
        self.assertEqual((self.root/'out/node_modules/x.js').read_bytes(),b'hello')
        self.assertFalse((self.root/'out/account.json').exists())

    @unittest.skipUnless(os.name == 'nt', 'Windows installer extraction')
    def test_tampered_official_file_is_rejected_before_any_execution(self):
        source=self.root/'client.exe';source.write_bytes(b'wrong')
        with patch('connection_setup.subprocess.run') as run,patch('connection_setup.download') as transfer:
            with self.assertRaises(ControlError):prepare(self.root/'profile',installer=source)
        run.assert_not_called();transfer.assert_not_called()
        self.assertEqual(list((self.root/'profile/connection').iterdir()),[])

    @unittest.skipUnless(os.name == 'nt', 'Windows installer extraction')
    def test_cancel_before_transfer_does_not_execute_or_leave_staging(self):
        cancel=threading.Event();cancel.set()
        with patch('connection_setup.subprocess.run') as run,patch('connection_setup.download') as transfer:
            with self.assertRaisesRegex(ControlError,'annulée'):prepare(self.root/'profile',cancel=cancel)
        run.assert_not_called();transfer.assert_not_called()
        self.assertEqual(list((self.root/'profile/connection').iterdir()),[])

    def fake_session(self,response):
        session=MagicMock()
        session.__enter__.return_value=session
        session.get.return_value.__enter__.return_value=response
        return patch('connection_setup.requests.Session',return_value=session),session

    def test_bad_download_is_deleted_and_error_does_not_echo_body(self):
        response=MagicMock(status_code=200,headers={})
        response.iter_content.return_value=[b'PRIVATE-NOT-OFFICIAL']
        context,session=self.fake_session(response)
        target=self.root/'download.exe'
        with context,self.assertRaises(ControlError) as failure:
            download(self.artifact(),target,lambda message:None)
        self.assertFalse(target.exists());self.assertNotIn('PRIVATE',str(failure.exception))

    def test_redirect_to_untrusted_or_plain_http_host_is_never_followed(self):
        for location in ('https://untrusted.example/payload','http://downloads.action.com/test.exe','https://user@downloads.action.com/a'):
            response=MagicMock(status_code=302,headers={'Location':location})
            context,session=self.fake_session(response)
            with self.subTest(location=location),context,self.assertRaises(ControlError):
                download(self.artifact(),self.root/'download.exe',lambda message:None)
            self.assertEqual(session.get.call_count,1)

    def test_successful_transfer_is_hash_checked(self):
        response=MagicMock(status_code=200,headers={'Content-Length':'8'})
        response.iter_content.return_value=[b'offi',b'cial']
        context,session=self.fake_session(response);target=self.root/'download.exe'
        with context:download(self.artifact(),target,lambda message:None)
        verify_file(target,self.artifact())
        self.assertFalse(session.get.call_args.kwargs['allow_redirects'])

    def test_empty_profile_has_no_hidden_developer_identity_fallback(self):
        with patch('lsc_account.HOME',self.root),patch.dict(os.environ,{},clear=True):
            self.assertIsNone(portable_identity_path())
            self.assertFalse(connection_ready())
            with self.assertRaises(ControlError): runtime_root()


class LoginSetupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        with patch('lsc_login.QTimer.singleShot'):
            self.dialog=LSCLogin(MagicMock())
        self.dialog.timer.stop()

    def tearDown(self):
        self.dialog.reject()
        self.dialog.deleteLater()
        self.app.processEvents()

    def test_first_run_offers_setup_instead_of_private_module_import(self):
        with patch('lsc_login.connection_ready',return_value=False):self.dialog.start()
        self.assertFalse(self.dialog.prepare_button.isHidden())
        self.assertFalse(self.dialog.installer_button.isHidden())
        self.assertTrue(self.dialog.refresh_button.isHidden())
        self.assertIn('64 Mo',self.dialog.status.text())
        self.assertFalse(hasattr(self.dialog,'import_button'))

    def test_ready_profile_requests_qr_without_preparing_again(self):
        account=MagicMock();account.connected=False
        with patch('lsc_login.connection_ready',return_value=True),patch('lsc_login.LSCAccount',return_value=account),patch.object(self.dialog,'submit') as submit:
            self.dialog.start()
        self.assertTrue(self.dialog.prepare_button.isHidden())
        self.assertEqual(submit.call_args.args[0],'create')

    def test_preparation_failure_keeps_retry_controls_and_no_qr(self):
        self.dialog.complete('prepare',None,'Téléchargement indisponible')
        self.assertTrue(self.dialog.prepare_button.isEnabled())
        self.assertTrue(self.dialog.installer_button.isEnabled())
        self.assertIsNone(self.dialog.token)

    def test_successful_preparation_continues_to_real_login_flow(self):
        with patch.object(self.dialog,'start') as start:
            self.dialog.complete('prepare',Path('local-runtime'),None)
        start.assert_called_once()

    def test_close_cancels_pending_setup(self):
        self.dialog.reject()
        self.assertTrue(self.dialog.cancel.is_set())


if __name__=='__main__':unittest.main()

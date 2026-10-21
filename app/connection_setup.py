"""Prepare the official client locally. No vendor binary or identity is redistributed.

Only pinned archives are accepted. Installers are read as archives, never launched.
The verified Electron runtime later executes our bundled, restricted native bridge.
"""
import ast
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import uuid
from urllib.parse import urlparse
import requests
from core import ControlError

OFFICIAL_PAGE = 'https://www.action.com/fr-fr/brand/battletron-lsc-smart-gaming/'
CLIENT = dict(url='https://downloads.action.com/battletron/lsc_battletron_2.0.17.exe',
              size=61587131, sha256='2deb33830cf0a2b93c888f747bec3512054b420b03e8288bde53b889efc78cfd')
READER = dict(url='https://github.com/ip7z/7zip/releases/download/26.04/7z2604-x64.msi',
              size=2009088, sha256='0b01334a418654293513449f61d6bfc99e5196ca371e3c3dc961eda57cd535c6')
READER_FILES = {'7z.exe':'95fff19b73eff77c87c0d7bd32822e43fb90dd2932459f962eb532d8dfb6ba53',
                '7z.dll':'899cd73d7fc60e1c1c35c7de0f5bed3dc69bfe2cecbd48014d868a347970a0b1'}
DOWNLOAD_HOSTS = frozenset(('downloads.action.com','github.com','release-assets.githubusercontent.com'))
DEFAULT_FIELDS = frozenset(('appRnVersion','appVersion','channel','clientId','deviceId','et','lang',
                            'os','osSystem','platform','sdkVersion','timeZoneId','ttid'))


def runtime_path(home):
    return Path(home) / 'connection' / 'battletron-2.0.17'


def check_cancel(cancel):
    if cancel is not None and cancel.is_set():
        raise ControlError('Préparation annulée.')


def verify_file(path, artifact):
    path = Path(path)
    if not path.is_file() or path.stat().st_size != artifact['size']:
        raise ControlError('Le fichier officiel ne correspond pas à la version attendue.')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    if digest.hexdigest() != artifact['sha256']:
        raise ControlError('Empreinte du fichier officiel incorrecte. Aucune préparation effectuée.')


def download(artifact, target, progress, cancel=None):
    target = Path(target)
    try:
        with requests.Session() as session:
            session.headers.update({'User-Agent':'LSC-Control/0.3.0 (Windows; interoperability setup)', 'Referer':OFFICIAL_PAGE})
            url = artifact['url']
            for _ in range(4):
                parsed = urlparse(url)
                if parsed.scheme != 'https' or parsed.hostname not in DOWNLOAD_HOSTS or parsed.username or parsed.password:
                    raise ControlError('Source de téléchargement non autorisée.')
                check_cancel(cancel)
                with session.get(url,stream=True,timeout=(10,30),allow_redirects=False) as response:
                    if response.status_code in (301,302,303,307,308):
                        url = response.headers.get('Location','')
                        continue
                    if response.status_code != 200:
                        raise ControlError('Téléchargement officiel indisponible. Réessaie ou choisis le programme officiel déjà téléchargé.')
                    length = response.headers.get('Content-Length')
                    if length and int(length) != artifact['size']:
                        raise ControlError('Taille du téléchargement officiel inattendue.')
                    received, last = 0, -1
                    with target.open('wb') as output:
                        for block in response.iter_content(65536):
                            check_cancel(cancel)
                            received += len(block)
                            if received > artifact['size']:
                                raise ControlError('Téléchargement officiel trop volumineux.')
                            output.write(block)
                            percent = received * 100 // artifact['size']
                            if percent != last:
                                progress(f'Téléchargement : {percent} %')
                                last = percent
                    verify_file(target,artifact)
                    return
            raise ControlError('Trop de redirections du téléchargement officiel.')
    except requests.RequestException:
        raise ControlError('Téléchargement impossible. Vérifie Internet et réessaie.') from None
    except (OSError,ValueError):
        raise ControlError('Impossible de préparer le téléchargement officiel.') from None
    finally:
        # A failed transfer must never be reused as a valid cached component.
        if target.exists():
            try: verify_file(target, artifact)
            except ControlError: target.unlink(missing_ok=True)


def extract_cab(msi_path, output):
    """Read one pinned MSI stream using Windows Installer in read-only mode."""
    from ctypes import wintypes
    msi = ctypes.WinDLL('msi')
    msi.MsiOpenDatabaseW.argtypes=[wintypes.LPCWSTR,ctypes.c_void_p,ctypes.POINTER(wintypes.UINT)]
    msi.MsiDatabaseOpenViewW.argtypes=[wintypes.UINT,wintypes.LPCWSTR,ctypes.POINTER(wintypes.UINT)]
    msi.MsiViewExecute.argtypes=[wintypes.UINT,wintypes.UINT]
    msi.MsiViewFetch.argtypes=[wintypes.UINT,ctypes.POINTER(wintypes.UINT)]
    msi.MsiRecordReadStream.argtypes=[wintypes.UINT,wintypes.UINT,ctypes.c_void_p,ctypes.POINTER(wintypes.DWORD)]
    handles = []
    try:
        database,view,record = wintypes.UINT(),wintypes.UINT(),wintypes.UINT()
        if msi.MsiOpenDatabaseW(str(Path(msi_path).resolve()),None,ctypes.byref(database)) != 0: raise ValueError()
        handles.append(database)
        if msi.MsiDatabaseOpenViewW(database,"SELECT `Data` FROM `_Streams` WHERE `Name` = 'product.cab'",ctypes.byref(view)) != 0: raise ValueError()
        handles.append(view)
        if msi.MsiViewExecute(view,0) != 0 or msi.MsiViewFetch(view,ctypes.byref(record)) != 0: raise ValueError()
        handles.append(record)
        with Path(output).open('wb') as stream:
            total = 0
            while True:
                buffer=ctypes.create_string_buffer(65536); size=wintypes.DWORD(len(buffer))
                if msi.MsiRecordReadStream(record,1,buffer,ctypes.byref(size)) != 0: raise ValueError()
                if not size.value: break
                total += size.value
                if total > READER['size']: raise ValueError()
                stream.write(buffer.raw[:size.value])
    finally:
        for handle in reversed(handles): msi.MsiCloseHandle(handle)


class Asar:
    def __init__(self,path):
        self.path = Path(path)
        with self.path.open('rb') as stream:
            fields=struct.unpack('<4I',stream.read(16))
            if fields[0]!=4 or not 0 < fields[3] <= 8*1024*1024: raise ValueError()
            self.header=json.loads(stream.read(fields[3]))
            self.start=8+fields[1]
        self.entries={}
        self._walk(self.header['files'])

    def _walk(self, entries, prefix=''):
        for name, entry in entries.items():
            if name in ('.','..') or any(c in name for c in '/\\:') or not name: raise ValueError()
            path=prefix+name
            if 'files' in entry: self._walk(entry['files'],path+'/')
            else:
                if entry.get('unpacked') or 'link' in entry: raise ValueError()
                self.entries[path]=entry

    def read(self,name):
        entry=self.entries[name]
        offset,size=int(entry['offset']),int(entry['size'])
        if offset < 0 or not 0 <= size <= 32*1024*1024 or self.start+offset+size>self.path.stat().st_size: raise ValueError()
        with self.path.open('rb') as stream:
            stream.seek(self.start+offset)
            return stream.read(size)

    def extract_modules(self,destination):
        root=Path(destination).resolve()
        for name in self.entries:
            if not name.startswith('node_modules/'): continue
            target=(root/name).resolve()
            if not target.is_relative_to(root): raise ValueError()
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(self.read(name))


def identity_from_source(source):
    """Parse only literal configuration, never eval vendor JavaScript."""
    def literal(name):
        match=re.search(r'export\s+const\s+'+name+r'\s*=\s*("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')\s*;',source)
        if not match: raise ValueError()
        value=ast.literal_eval(match[1])
        if not isinstance(value,str) or not value: raise ValueError()
        return value
    appkey,secret=literal('APPKEY'),literal('APPSECRET')
    match=re.search(r'POST_DEFAULTPARAMS\s*=\s*\{([^}]+)\}',source)
    if not match: raise ValueError()
    defaults={}
    for line in match[1].splitlines():
        line=line.strip()
        if not line: continue
        field=re.fullmatch(r'(\w+)\s*:\s*(.+?),?',line)
        if not field or field[1] not in DEFAULT_FIELDS: raise ValueError()
        token=field[2].rstrip(',').strip()
        value=appkey if token=='APPKEY' else ast.literal_eval(token)
        if not isinstance(value,str): raise ValueError()
        defaults[field[1]]=value
    if set(defaults)!=DEFAULT_FIELDS: raise ValueError()
    # A new installation must not inherit the vendor sample's fixed device ID.
    defaults.update(deviceId=str(uuid.uuid4()),lang='fr',timeZoneId='Europe/Paris')
    return dict(APPKEY=appkey,APPSECRET=secret,defaults=defaults)


def prepare(home, progress=lambda text:None, cancel=None, installer=None):
    if os.name != 'nt': raise ControlError('La préparation automatique est disponible sous Windows.')
    base=(Path(home)/'connection').resolve()
    base.mkdir(parents=True,exist_ok=True)
    staging=Path(tempfile.mkdtemp(prefix='prepare-',dir=base)).resolve()
    if staging.parent != base: raise ControlError('Dossier de préparation invalide.')
    try:
        check_cancel(cancel)
        client=staging/'official-client.exe'
        if installer:
            verify_file(installer,CLIENT)
            shutil.copyfile(installer,client)
        else:
            progress('Téléchargement du composant officiel Action…')
            download(CLIENT,client,progress,cancel)
        reader=staging/'reader.msi'
        progress('Préparation du lecteur d’archives…')
        download(READER,reader,progress,cancel)
        cab=staging/'reader.cab'
        extract_cab(reader,cab)
        reader_dir=staging/'reader';reader_dir.mkdir()
        def run(*args):
            check_cancel(cancel)
            subprocess.run([str(a) for a in args],check=True,timeout=120,stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
            check_cancel(cancel)
        system=Path(os.environ.get('SystemRoot','C:/Windows'))/'System32'
        run(system/'expand.exe',cab,'-F:*',reader_dir)
        for name,digest in READER_FILES.items():
            source=reader_dir/('_'+name)
            if hashlib.sha256(source.read_bytes()).hexdigest()!=digest: raise ValueError()
            source.rename(reader_dir/name)
        progress('Extraction locale du composant officiel…')
        outer=staging/'outer'; outer.mkdir()
        run(reader_dir/'7z.exe','x','-y','-bso0','-bsp0',client,'$PLUGINSDIR/app-32.7z','-o'+str(outer))
        archive=outer/'$PLUGINSDIR/app-32.7z'
        prepared=staging/'runtime'; (prepared/'app').mkdir(parents=True)
        run(reader_dir/'7z.exe','x','-y','-bso0','-bsp0',archive,'-o'+str(prepared/'app'))
        asar=Asar(prepared/'app/resources/app.asar')
        source_map=json.loads(asar.read('js/app.2ebba8d3.js.map'))
        candidates=[content for name,content in zip(source_map['sources'],source_map['sourcesContent']) if name.endswith('/src/configs/index.js')]
        if len(candidates)!=1: raise ValueError()
        identity=identity_from_source(candidates[0])
        interop=prepared/'interop'; interop.mkdir()
        asar.extract_modules(interop)
        identity_file=interop/'client-identity.json'
        identity_file.write_text(json.dumps(identity,ensure_ascii=False),encoding='utf-8')
        os.chmod(identity_file,0o600)
        for required in ('app/LSC_Battletron.exe','app/resources/static/dll/jnimain.dll','interop/node_modules/ffi-napi/package.json'):
            if not (prepared/required).is_file(): raise ValueError()
        (prepared/'provenance.json').write_text(json.dumps({'client':CLIENT,'reader':READER,'source_page':OFFICIAL_PAGE}),encoding='utf-8')
        check_cancel(cancel)
        target=runtime_path(home).resolve()
        if target.parent!=base: raise ValueError()
        if target.exists():
            # Never overwrite a functioning or user-modified runtime silently.
            raise ControlError('Le composant existe déjà. Ferme puis rouvre la connexion.')
        prepared.rename(target)
        progress('Connexion prête. Demande du QR code…')
        return target
    except ControlError:
        raise
    except (OSError,ValueError,KeyError,TypeError,struct.error,subprocess.SubprocessError):
        raise ControlError('Préparation du composant officiel impossible. Aucun installateur n’a été exécuté.') from None
    finally:
        if staging.parent==base and staging.name.startswith('prepare-'):
            shutil.rmtree(staging,ignore_errors=True)

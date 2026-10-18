/* Personal, unsupported interoperability helper. No credential logging. */
'use strict';
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const https = require('https');
const readline = require('readline');
const root = process.argv[2];
const ffi = require(path.join(root, 'interop/node_modules/ffi-napi'));
const ref = require(path.join(root, 'interop/node_modules/ref-napi'));
const win = ffi.Library('kernel32', {
  GetStdHandle: ['pointer', ['uint']],
  GetCurrentProcess: ['pointer', []],
  DuplicateHandle: ['bool', ['pointer','pointer','pointer','pointer','uint','bool','uint']],
  WriteFile: ['bool', ['pointer','pointer','uint','pointer','pointer']],
});
const originalPipe = ref.alloc('pointer');
const processHandle = win.GetCurrentProcess();
if (!win.DuplicateHandle(processHandle, win.GetStdHandle(0xfffffff5), processHandle,
  originalPipe, 0, false, 2)) throw new Error('HELPER_PIPE');
function send(value) {
  const buffer = Buffer.from(JSON.stringify(value) + '\n');
  const written = ref.alloc('uint');
  if (!win.WriteFile(originalPipe.deref(), buffer, buffer.length, written, ref.NULL)
      || written.deref() !== buffer.length) process.exit(1);
}
// This vendor DLL prints sensitive values through the C runtime. Close its
// stdout/stderr before loading it; Node's already-open pipe remains our channel.
const crt = ffi.Library('ucrtbase', {
  __acrt_iob_func: ['pointer', ['uint']],
  freopen_s: ['int', ['pointer', 'string', 'string', 'pointer']],
});
for (const descriptor of [1, 2]) {
  const filePointer = ref.alloc('pointer');
  if (crt.freopen_s(filePointer, 'NUL', 'w', crt.__acrt_iob_func(descriptor)) !== 0) {
    throw new Error('NATIVE_OUTPUT');
  }
}
const identity = JSON.parse(fs.readFileSync(path.join(root, 'interop/client-identity.json'), 'utf8'));
const dllPath = path.join(root, 'app/resources/static/dll');
const dll = ffi.Library(path.join(dllPath, 'jnimain.dll'), {
  setSecretContent: ['long', ['pointer', 'int']],
  getEncryptoKey: ['void', ['string', 'int', 'string', 'pointer']],
  doCommand: ['void', ['int', 'string', 'int', 'string', 'bool', 'bool', 'pointer']],
});
const picture = fs.readFileSync(path.join(dllPath, 't_s_online.bmp'));
if (dll.setSecretContent(picture, picture.length) !== 0) throw new Error('NATIVE_INIT');
function command(number, input, key = null) {
  // A SHA-256 signature needs 64 ASCII bytes plus its terminating NUL.
  // The original client's 64-byte allocation can corrupt the native heap.
  const output = Buffer.alloc(256);
  dll.doCommand(number, input, Buffer.byteLength(input), key, false, false, output);
  return ref.readCString(output, 0);
}
command(0, identity.APPSECRET, identity.APPKEY);
function secretFor(requestId, ecode) {
  const output = Buffer.alloc(64);
  dll.getEncryptoKey(requestId, requestId.length, ecode || null, output);
  const value = ref.readCString(output, 0);
  if (Buffer.byteLength(value) !== 16) throw new Error('NATIVE_KEY');
  return value;
}
const signedKeys = new Set(['a','v','lat','lon','lang','deviceId','appVersion','ttid',
  'isH5','h5Token','os','clientId','postData','time','requestId','et','n4h5','sid','chKey','sp']);
const allowed = new Set(['tuya.m.user.qr.token.create','tuya.m.user.qr.token.user.get',
  'tuya.m.location.list','tuya.m.location.get','tuya.m.my.group.device.list',
  'tuya.m.device.ref.info.list','tuya.m.device.get','tuya.m.device.dp.publish',
  'thing.m.timer.all.list','tuya.m.timer.all.list','thing.m.timer.category.list',
  'tuya.m.timer.category.list','thing.m.clock.dps.add','thing.m.clock.dps.update',
  'thing.m.clock.batch.status.update']);
const hosts = {eu: 'a1.tuyaeu.com', us: 'a1.tuyaus.com', cn: 'a1.tuyacn.com'};
const md5 = value => crypto.createHash('md5').update(value).digest('hex');
function formSignature(data) {
  const parts = Object.keys(data).sort().filter(k => signedKeys.has(k)).map(k => {
    let v = data[k];
    if (k === 'postData') {
      const h = md5(v);
      v = h.slice(8,16) + h.slice(0,8) + h.slice(24,32) + h.slice(16,24);
    }
    return `${k}=${v}`;
  });
  const sign = command(1, parts.join('||'));
  if (!/^[a-fA-F0-9]{32,128}$/.test(sign)) throw new Error('NATIVE_SIGN');
  return sign;
}
function transport(host, data) {
  return new Promise((resolve, reject) => {
    const body = new URLSearchParams(data).toString();
    const request = https.request({hostname:host, path:'/api.json', method:'POST',
      headers:{'Content-Type':'application/x-www-form-urlencoded',
        'Content-Length':Buffer.byteLength(body)}, timeout:20000}, response => {
      let payload = '', size = 0;
      response.on('data', bytes => {
        size += bytes.length;
        if (size > 8*1024*1024) { response.destroy(); reject(new Error('RESPONSE_SIZE')); }
        else payload += bytes;
      });
      response.on('end', () => {
        if (response.statusCode !== 200) return reject(new Error('HTTP_' + response.statusCode));
        try { resolve(JSON.parse(payload)); } catch (_) { reject(new Error('RESPONSE_JSON')); }
      });
      response.on('error', () => reject(new Error('NETWORK')));
    });
    request.on('timeout', () => request.destroy(new Error('TIMEOUT')));
    request.on('error', e => reject(new Error(e.message === 'TIMEOUT' ? 'TIMEOUT' : 'NETWORK')));
    request.end(body);
  });
}
async function call(input) {
  if (input.test) {
    const s = secretFor(crypto.randomUUID ? crypto.randomUUID() : crypto.randomBytes(16).toString('hex'), null);
    return {native:true, keyLength:Buffer.byteLength(s), signAvailable:!!command(1,'a=test||v=1.0')};
  }
  if (!allowed.has(input.api) || !hosts[input.region]) throw new Error('REQUEST_NOT_ALLOWED');
  const session = input.session || {};
  const requestId = [4,2,2,2,6].map(n => crypto.randomBytes(n).toString('hex')).join('-');
  const key = secretFor(requestId, session.ecode);
  const data = Object.assign({}, identity.defaults, input.gid ? {gid:input.gid} : {},
    session.sid ? {sid:session.sid} : {}, {a:input.api,v:input.version||'1.0',requestId});
  if (input.timezoneId) data.timeZoneId=input.timezoneId;
  if (input.data && Object.keys(input.data).length) {
    const cipher = crypto.createCipheriv('aes-128-ecb', Buffer.from(key), null);
    data.postData = Buffer.concat([cipher.update(JSON.stringify(input.data),'utf8'),cipher.final()]).toString('base64');
  }
  data.sign = formSignature(data);
  const raw = await transport(hosts[input.region], data);
  if (raw.errorCode) throw new Error('SERVER_' + String(raw.errorCode).replace(/[^A-Za-z0-9_]/g,''));
  if (typeof raw.result !== 'string' || typeof raw.sign !== 'string') throw new Error('RESPONSE_FORMAT');
  const expected = md5(`result=${raw.result}||t=${raw.t}||${key}`);
  if (!/^[a-f0-9]{32}$/.test(raw.sign) || !crypto.timingSafeEqual(Buffer.from(expected),Buffer.from(raw.sign))) {
    throw new Error('RESPONSE_SIGNATURE');
  }
  const decipher = crypto.createDecipheriv('aes-128-ecb',Buffer.from(key),null);
  const result = JSON.parse(Buffer.concat([decipher.update(Buffer.from(raw.result,'base64')),decipher.final()]).toString('utf8'));
  if (!result.success) throw new Error('SERVER_' + String(result.errorCode || 'REFUSED').replace(/[^A-Za-z0-9_]/g,''));
  return result.result;
}
let queue = Promise.resolve();
readline.createInterface({input:process.stdin,crlfDelay:Infinity}).on('line', line => {
  queue = queue.then(async () => {
    let id = null;
    try {
      const input = JSON.parse(line);
      id = input.id;
      const result = await call(input);
      send({id,ok:true,result});
    } catch (e) {
      const code = /^[A-Z0-9_]+$/.test(e.message) ? e.message : 'HELPER_ERROR';
      send({id,ok:false,error:code});
    }
  });
});

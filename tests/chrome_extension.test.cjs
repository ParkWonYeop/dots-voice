const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function environment(options = {}) {
  const {ready = false, failOffer = false, holdStart = false} = options;
  const url = Object.hasOwn(options, 'url') ? options.url : 'https://chatgpt.com/dots/example';
  const calls = [];
  let listener;
  let receive;
  let release;
  const chrome = {
    runtime: {
      id: 'test', getURL: name => `chrome-extension://test/${name}`,
      sendMessage: async message => {calls.push(['progress', message.step]); throw Error('popup closed');},
      onMessage: {addListener: fn => {listener = fn;}},
      connectNative: name => {
        calls.push(['native', name]);
        return {
          onMessage: {addListener: fn => {receive = fn;}},
          onDisconnect: {addListener() {}}, disconnect() {calls.push(['disconnect']);},
          postMessage(message) {
            calls.push(['request', message.type]);
            const reply = () => receive({id: message.id, ok: !(failOffer && message.type === 'offer'),
              error: 'offer failed', result: message.type === 'offer' ? {type: 'answer', sdp: 'v=0'} : {reused: true}});
            if (holdStart && message.type === 'start') release = reply;
            else queueMicrotask(reply);
          }
        };
      }
    },
    tabs: {get: async id => ({id, url}), onUpdated: {addListener() {}}},
    action: {setBadgeText: async ({text}) => {calls.push(['badge', text]);}, setBadgeBackgroundColor: async () => {}},
    scripting: {executeScript: async options => {
      calls.push(['inject', options.func?.name || 'files', options.target]);
      let result = null;
      if (options.func?.name === 'readStatus') result = ready ? {ready: true, version: 1} : null;
      if (options.func?.name === 'getOffer') result = {type: 'offer', sdp: 'v=0'};
      if (options.func?.name === 'applyAnswer') result = {ready: true, speaker: 'designed_soft'};
      return [{documentId: 'original-document', result}];
    }}
  };
  const source = fs.readFileSync(__dirname + '/../chrome-extension/background.js', 'utf8').replace(/^import .*;\n/, '') +
    '\n';
  const names = ['readStatus', 'removeHook', 'getOffer', 'applyAnswer', 'testVoice'];
  const functions = Object.fromEntries(names.map(name => [name, {[name]() {}}[name]]));
  vm.runInNewContext(source, {chrome, ...functions, URL, setTimeout, clearTimeout, console});
  const send = (type, sender = {id: 'test', url: 'chrome-extension://test/popup.html'}) =>
    new Promise(resolve => {const accepted = listener({type, tabId: 7}, sender, resolve); if (!accepted) resolve(null);});
  return {calls, send, release: () => release()};
}

(async () => {
  let env = environment();
  const [first, second] = await Promise.all([env.send('enable'), env.send('enable')]);
  assert.equal(first.ok, true);
  assert.equal(second.ok, true);
  assert.deepEqual(env.calls.filter(x => x[0] === 'request').map(x => x[1]), ['start', 'offer']);
  assert.equal(env.calls.filter(x => x[0] === 'native').length, 1, 'concurrent clicks share one connection');
  for (const call of env.calls.filter(x => x[0] === 'inject' && x[1] !== 'readStatus')) {
    assert.equal(call[2].documentIds[0], 'original-document', 'never follow navigation to another document');
  }
  assert.deepEqual(env.calls.filter(x => x[0] === 'progress').map(x => x[1]), ['server', 'page', 'voice'],
    'popup progress survives a closed popup');
  assert.deepEqual(env.calls.filter(x => x[0] === 'badge').map(x => x[1]), ['ON']);
  // A reopened popup reads the step of the connection already in progress, without a second host.
  env = environment({holdStart: true});
  const connecting = env.send('enable');
  await new Promise(resolve => setTimeout(resolve, 0));
  const during = await env.send('status');
  assert.deepEqual(JSON.parse(JSON.stringify(during)), {ok: true, result: {step: 'server', page: null}});
  assert.equal((await env.send('test')).ok, false, 'other actions wait for the connection');
  env.release();
  assert.equal((await connecting).ok, true);
  assert.deepEqual(JSON.parse(JSON.stringify(await env.send('status'))), {ok: true, result: {step: null, page: null}});
  assert.equal(env.calls.filter(x => x[0] === 'native').length, 1);
  env = environment({ready: true});
  assert.equal((await env.send('enable')).ok, true);
  assert.equal(env.calls.filter(x => x[0] === 'native').length, 0);
  env = environment({url: 'https://example.com/dots/private'});
  assert.equal((await env.send('enable')).ok, false);
  assert.equal(env.calls.length, 0);
  assert.equal(await env.send('enable', {id: 'test', url: 'https://chatgpt.com/dots/example'}), null);
  for (const url of [undefined, null, '', ' ', 'not a URL', 'chrome://extensions/', 'https://chatgpt.com/', 'https://chatgpt.com/dots-other', 'https://chatgpt.com.evil.example/dots/test']) {
    env = environment({url});
    for (const action of ['enable', 'status', 'test', 'disable']) {
      const response = await env.send(action);
      assert.equal(response.ok, false);
      assert.match(response.error, /dots 대화 탭으로 이동/);
      assert.equal(response.code, 'wrong-tab');
      assert.doesNotMatch(response.error, /Invalid URL/);
    }
    assert.equal(env.calls.length, 0, 'invalid/restricted tab must not start the server or inject scripts');
  }
  env = environment({failOffer: true});
  assert.equal((await env.send('enable')).ok, false);
  assert.equal(env.calls.filter(x => x[0] === 'inject' && x[1] === 'removeHook').length, 2, 'restore after failure');
  assert.deepEqual(env.calls.filter(x => x[0] === 'badge').map(x => x[1]), ['!']);
  console.log('Chrome connection checks passed: one-click flow, progress steps, status while connecting, duplicate clicks, document pinning, restricted/missing URLs, origin restriction, failure restore.');
})().catch(error => {console.error(error); process.exit(1);});

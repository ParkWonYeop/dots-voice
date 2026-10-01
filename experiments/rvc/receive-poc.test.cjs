// Local mocks only; never opens Chrome or a call.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(__dirname + '/receive-poc.js', 'utf8');

async function scenario({ renderer = true, creation = 'dom', resumeFails = false, connectFails = false,
  constructorFails = false, suspendedLater = false, unmutedLater = false,
  restoreDuringResume = false } = {}) {
  const intervals = new Set();
  const mic = { kind: 'audio', stop() { throw Error('mic stopped'); } };
  const receive = { kind: 'audio', readyState: 'live', stop() { throw Error('receive stopped'); } };
  class Stream {
    constructor(tracks) { this.tracks = tracks; }
    getAudioTracks() { return this.tracks.filter(t => t.kind === 'audio'); }
  }
  const receiveStream = new Stream([receive]);
  const element = { isConnected: true, srcObject: receiveStream, paused: false, muted: false, volume: 1 };
  class PC {
    constructor() { this.listeners = {}; this.senderTrack = mic; }
    addEventListener(type, callback) { this.listeners[type] = callback; }
    removeEventListener(type, callback) { if (this.listeners[type] === callback) delete this.listeners[type]; }
    emit(track) { this.listeners.track?.({ track }); }
  }
  let closes = 0;
  let sources = 0;
  let context;
  class Context {
    constructor() { if (constructorFails) throw Error('context failed'); context = this; }
    state = 'running';
    createMediaStreamSource() {
      sources++;
      return { connect: () => {
        if (connectFails) throw Error('connect failed');
        return { connect() {} };
      }, disconnect() {} };
    }
    createGain() { return { gain: { value: 1 }, disconnect() {} }; }
    resume() {
      if (restoreDuringResume) queueMicrotask(() => window.__dotReceivePoc.restore());
      return resumeFails ? Promise.reject(Error('resume failed')) : Promise.resolve();
    }
    close() { closes++; return Promise.resolve(); }
  }
  const NativeAudio = function Audio() { return element; };
  const window = { RTCPeerConnection: PC, Audio: NativeAudio };
  const document = { createElement: () => creation === 'duplicate' ? { ...element } : element };
  const NativeCreateElement = document.createElement;
  const scope = {
    window, AudioContext: Context, MediaStream: Stream,
    document,
    setInterval: fn => { intervals.add(fn); return fn; },
    clearInterval: fn => intervals.delete(fn),
    setTimeout: () => 1,
    console: { info() {}, warn() {} }
  };
  vm.runInNewContext(source, scope);
  const firstApi = window.__dotReceivePoc;
  if (renderer && creation === 'dom') document.createElement('audio');
  if (renderer && creation === 'new') new window.Audio();
  if (renderer && creation === 'duplicate') {
    document.createElement('audio');
    document.createElement('audio');
  }
  const pc = new window.RTCPeerConnection();
  assert.equal(pc.senderTrack, mic);
  pc.emit(receive);
  pc.emit(receive); // simultaneous duplicate track events must not build two graphs
  for (let i = 0; i < 60; i++) {
    for (const fn of [...intervals]) fn();
    await Promise.resolve();
  }
  await Promise.resolve();
  if (suspendedLater) { context.state = 'suspended'; for (const fn of [...intervals]) fn(); }
  if (unmutedLater) { element.muted = false; for (const fn of [...intervals]) fn(); }
  return { scope, window, document, NativeAudio, NativeCreateElement,
    PC, pc, element, firstApi, intervals,
    getCloses: () => closes, getSources: () => sources };
}

(async () => {
  const missing = await scenario({ renderer: false });
  assert.equal(missing.firstApi.status().state, 'failed-closed');
  assert.equal(missing.element.muted, false);
  missing.firstApi.restore();
  assert.equal(missing.window.RTCPeerConnection, missing.PC);
  assert.equal(missing.pc.listeners.track, undefined);
  assert.equal(missing.document.createElement, missing.NativeCreateElement);
  assert.equal(missing.window.Audio, missing.NativeAudio);

  const unobserved = await scenario({ creation: 'preexisting' });
  assert.equal(unobserved.firstApi.status().state, 'failed-closed');
  assert.equal(unobserved.element.muted, false);
  unobserved.firstApi.restore();
  const duplicate = await scenario({ creation: 'duplicate' });
  assert.equal(duplicate.firstApi.status().state, 'failed-closed');
  assert.equal(duplicate.element.muted, false);
  duplicate.firstApi.restore();

  for (const option of [{ resumeFails: true }, { connectFails: true }, { constructorFails: true }]) {
    const failed = await scenario(option);
    assert.equal(failed.firstApi.status().state, 'failed-closed');
    assert.equal(failed.element.muted, false);
    assert.equal(failed.getCloses(), option.constructorFails ? 0 : 1);
    failed.firstApi.restore();
  }

  const success = await scenario();
  assert.equal(success.firstApi.status().state, 'substitute-running');
  assert.equal(success.getSources(), 1);
  assert.equal(success.element.muted, true);
  success.firstApi.restore();
  assert.equal(success.element.muted, false);
  assert.equal(success.window.RTCPeerConnection, success.PC);
  assert.equal(success.document.createElement, success.NativeCreateElement);
  assert.equal(success.window.Audio, success.NativeAudio);
  assert.equal(success.pc.listeners.track, undefined);
  assert.equal(success.window.__dotReceivePoc, undefined);
  assert.equal(success.intervals.size, 0);
  vm.runInNewContext(source, success.scope);
  assert.ok(success.window.__dotReceivePoc);
  success.window.__dotReceivePoc.restore();
  const constructed = await scenario({ creation: 'new' });
  assert.equal(constructed.firstApi.status().state, 'substitute-running');
  constructed.firstApi.restore();
  for (const option of [{ suspendedLater: true }, { unmutedLater: true }]) {
    const changed = await scenario(option);
    assert.equal(changed.firstApi.status().state, 'failed-closed');
    assert.equal(changed.element.muted, false);
    changed.firstApi.restore();
  }
  const raced = await scenario({ restoreDuringResume: true });
  assert.equal(raced.element.muted, false);
  assert.equal(raced.window.RTCPeerConnection, raced.PC);
  assert.equal(raced.pc.listeners.track, undefined);
  console.log('mock tests passed');
})().catch(error => { console.error(error); process.exitCode = 1; });

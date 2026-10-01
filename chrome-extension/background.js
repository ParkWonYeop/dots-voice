import {readStatus, removeHook, getOffer, applyAnswer, testVoice} from './page-api.js';

const HOST = 'com.dots.local_voice';
const pending = new Map();
const progress = new Map();
const BADGES = {on: ['ON', '#7c5cff'], click: ['클릭', '#d97706'], error: ['!', '#e5484d'], off: ['', '#7c5cff']};
const DOTS_TAB_REQUIRED = 'dots 대화 탭으로 이동한 뒤 Chrome 도구 모음의 Dots Voice 버튼을 다시 눌러주세요. 설정·확장 관리 화면에서는 연결할 수 없어요.';

function requireDotsTab(tab) {
  // activeTab intentionally omits url on restricted pages (e.g. chrome://).
  // Keep the temporary grant; broader tabs/host permissions are unnecessary.
  let url;
  try {
    if (typeof tab?.url !== 'string' || !tab.url.trim()) throw Error();
    url = new URL(tab.url);
  } catch {
    url = null;
  }
  if (url?.origin !== 'https://chatgpt.com' || !/^\/dots(?:\/|$)/.test(url.pathname)) {
    throw Object.assign(Error(DOTS_TAB_REQUIRED), {code: 'wrong-tab'});
  }
}

function badge(tabId, kind) {
  const [text, color] = BADGES[kind];
  return Promise.all([chrome.action.setBadgeText({tabId, text}),
    chrome.action.setBadgeBackgroundColor({tabId, color})]).catch(() => {});
}

function badgeFor(page) {
  if (!page) return 'off';
  if (page.phase === 'fallback') return 'error';
  if (page.ready) return 'on';
  return page.phase === 'awaiting-audio-click' ? 'click' : 'off';
}

// The popup may be closed; it re-reads the current step through `status` when reopened.
function report(tabId, step) {
  progress.set(tabId, step);
  chrome.runtime.sendMessage({type: 'progress', tabId, step}).catch(() => {});
}

function connectHost() {
  const port = chrome.runtime.connectNative(HOST);
  const requests = new Map();
  let serial = 0;
  let disconnected = false;
  port.onMessage.addListener(message => {
    const request = requests.get(message.id);
    if (!request) return;
    requests.delete(message.id);
    clearTimeout(request.timer);
    if (message.ok) request.resolve(message.result);
    else request.reject(Error(message.error));
  });
  port.onDisconnect.addListener(() => {
    disconnected = true;
    const detail = chrome.runtime.lastError?.message || '연결이 종료됐습니다.';
    for (const request of requests.values()) {
      clearTimeout(request.timer);
      request.reject(Error('패키지의 설치 실행 파일을 실행했는지 확인하세요. ' + detail));
    }
    requests.clear();
  });
  return {
    request(type, extra = {}) {
      if (disconnected) return Promise.reject(Error('로컬 실행기가 연결되지 않았습니다.'));
      return new Promise((resolve, reject) => {
        const id = ++serial;
        const timer = setTimeout(() => {requests.delete(id); reject(Error('서버 응답 시간 초과'));}, type === 'start' ? 660000 : 30000);
        requests.set(id, {resolve, reject, timer});
        port.postMessage({id, type, ...extra});
      });
    },
    close() {port.disconnect();}
  };
}

async function run(target, func, args = []) {
  const results = await chrome.scripting.executeScript({target, world: 'MAIN', func, args});
  if (!results[0]) throw Error('dots 탭을 찾을 수 없습니다.');
  return results[0];
}

async function enable(tabId) {
  const first = await run({tabId, frameIds: [0]}, readStatus);
  const target = {tabId, documentIds: [first.documentId]};
  if (first.result?.ready && first.result.version === 1) return first.result;
  if (first.result?.phase === 'tts-running') throw Error('현재 통화를 끝낸 뒤 다시 연결하세요.');
  const host = connectHost();
  let installed = false;
  try {
    report(tabId, 'server');
    await host.request('start');
    report(tabId, 'page');
    // The documentId prevents navigation during model startup from targeting a new page.
    await run(target, removeHook);
    await chrome.scripting.executeScript({target, world: 'MAIN', files: ['transcript_buffer.js', 'dots-tts.js']});
    installed = true;
    const offer = (await run(target, getOffer)).result;
    report(tabId, 'voice');
    const answer = await host.request('offer', {offer});
    const result = (await run(target, applyAnswer, [answer])).result;
    await badge(tabId, result.ready ? 'on' : 'click');
    return result;
  } catch (error) {
    if (installed) await run(target, removeHook).catch(() => {});
    await badge(tabId, 'error');
    throw error;
  } finally {
    progress.delete(tabId);
    host.close();
  }
}

chrome.runtime.onMessage.addListener((message, sender, respond) => {
  if (sender.id !== chrome.runtime.id || sender.url !== chrome.runtime.getURL('popup.html')) return;
  (async () => {
    const tab = await chrome.tabs.get(message.tabId);
    requireDotsTab(tab);
    if (message.type === 'enable') {
      if (!pending.has(tab.id)) pending.set(tab.id, enable(tab.id).finally(() => pending.delete(tab.id)));
      return await pending.get(tab.id);
    }
    if (message.type === 'status') {
      const page = (await run({tabId: tab.id, frameIds: [0]}, readStatus)).result;
      if (!pending.has(tab.id)) await badge(tab.id, badgeFor(page));
      return {step: progress.get(tab.id) ?? null, page};
    }
    if (pending.has(tab.id)) throw Error('연결이 끝날 때까지 기다려주세요.');
    if (message.type === 'disable') {
      await run({tabId: tab.id, frameIds: [0]}, removeHook);
      await badge(tab.id, 'off');
      return {phase: 'restored'};
    }
    if (message.type === 'test') {
      await run({tabId: tab.id, frameIds: [0]}, testVoice);
      return {tested: true};
    }
    throw Error('Unknown action');
  })().then(result => respond({ok: true, result}), error => respond({ok: false, error: error.message, code: error.code}));
  return true;
});

chrome.tabs.onUpdated.addListener((tabId, change) => {
  if (change.status === 'loading') chrome.action.setBadgeText({tabId, text: ''}).catch(() => {});
});

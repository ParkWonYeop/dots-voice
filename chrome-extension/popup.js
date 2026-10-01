const $ = id => document.getElementById(id);
const title = $('title'), detail = $('detail'), errorBox = $('error'), steps = $('steps'), metrics = $('metrics');
const buttons = {connect: $('connect'), reload: $('reload'), test: $('test'), disable: $('disable')};
const STEPS = ['server', 'page', 'voice'];
const VIEWS = {
  checking: {title: '상태를 확인하고 있어요'},
  'wrong-tab': {title: 'dots 대화 탭에서 눌러주세요',
    detail: '설정·확장 관리 화면에서는 연결할 수 없어요. dots 대화를 연 뒤 도구 모음의 Dots Voice를 다시 눌러주세요.'},
  connecting: {title: '목소리를 연결하고 있어요',
    detail: '이 창을 닫아도 연결은 계속돼요. 처음에는 모델을 준비하느라 몇 분 걸릴 수 있어요.'},
  'needs-click': {title: '소리를 켜 주세요',
    detail: 'dots 페이지를 한 번 클릭하면 소리가 켜져요. 그다음 통화를 시작하세요.', buttons: ['disable']},
  ready: {title: '2번 목소리 연결 완료',
    detail: '이제 dots 통화를 시작하세요. 이미 통화 중이었다면 끊고 새로 시작해야 적용돼요.', buttons: ['test', 'disable']},
  'in-call': {title: '통화에 2번 목소리 적용 중',
    detail: '원래 음성은 음소거돼 있어요. 말을 시작하면 재생을 멈춰요.', buttons: ['test', 'disable']},
  off: {title: '원래 목소리를 쓰고 있어요', detail: '새 통화 전에 연결하면 2번 목소리로 들려요.', buttons: ['connect']},
  error: {title: '연결을 확인해 주세요', buttons: ['connect']},
  stale: {title: '확장 프로그램을 새로고침해 주세요',
    detail: '새 버전 파일이 설치됐지만 Chrome이 이전 버전을 실행 중이에요. 새로고침한 뒤 Dots Voice를 다시 눌러주세요.', buttons: ['reload']},
};
let tabId, state;
// Bumped by user actions so a slow background poll cannot overwrite a newer view.
let generation = 0, polling = false;

function render(name, extra = {}) {
  const view = {...VIEWS[name], ...extra};
  state = name;
  document.body.dataset.state = name;
  title.textContent = view.title;
  detail.textContent = view.detail || '';
  errorBox.textContent = view.error || '';
  errorBox.hidden = !view.error;
  metrics.textContent = view.metrics || '';
  metrics.hidden = !view.metrics;
  steps.hidden = name !== 'connecting';
  for (const [key, button] of Object.entries(buttons)) button.hidden = !view.buttons?.includes(key);
}

function setStep(step) {
  const current = STEPS.indexOf(step);
  for (const item of steps.children) {
    const index = STEPS.indexOf(item.dataset.step);
    item.className = index < current ? 'done' : index === current ? 'active' : '';
  }
}

async function request(type) {
  const response = await chrome.runtime.sendMessage({type, tabId});
  if (!response?.ok) throw Object.assign(Error(response?.error || '연결이 종료됐어요. 다시 눌러주세요.'), {code: response?.code});
  return response.result;
}

function fail(error) {
  if (error.code === 'wrong-tab') render('wrong-tab');
  // The installer replaced the files while Chrome kept the previous background worker.
  else if (error.message === 'Unknown action') render('stale');
  else render('error', {detail: error.message});
}

function showPage(page) {
  if (!page) return render('off');
  if (page.phase === 'fallback') {
    return render('error', {title: '로컬 목소리가 멈췄어요',
      detail: '원래 목소리로 자동 전환했어요. 통화를 끝낸 뒤 다시 연결하세요.', error: page.error});
  }
  if (page.ready) {
    const parts = [];
    if (page.generated) parts.push(`답변 ${page.generated}개 합성`);
    if (page.firstAudioMs != null) parts.push(`최근 첫 소리 ${(page.firstAudioMs / 1000).toFixed(2)}초`);
    return render(page.phase === 'tts-running' ? 'in-call' : 'ready', {metrics: parts.join(' · ')});
  }
  render(page.phase === 'awaiting-audio-click' ? 'needs-click' : 'off');
}

async function connect(step = 'server') {
  generation++;
  render('connecting');
  setStep(step);
  try {showPage(await request('enable'));}
  catch (error) {fail(error);}
}

async function poll() {
  if (polling || !['ready', 'in-call', 'needs-click'].includes(state)) return;
  polling = true;
  const seen = generation;
  try {
    const {page} = await request('status');
    if (seen === generation) showPage(page);
  } catch (error) {
    if (seen === generation) fail(error);
  } finally {polling = false;}
}

chrome.runtime.onMessage.addListener(message => {
  if (message.type === 'progress' && message.tabId === tabId && state === 'connecting') setStep(message.step);
});

buttons.connect.addEventListener('click', () => connect());
buttons.reload.addEventListener('click', () => chrome.runtime.reload());
buttons.test.addEventListener('click', async () => {
  const label = buttons.test.querySelector('span');
  buttons.test.disabled = true;
  label.textContent = '재생하는 중…';
  try {
    await request('test');
    await new Promise(resolve => setTimeout(resolve, 2500));
  } catch (error) {
    generation++;
    fail(error);
  } finally {
    buttons.test.disabled = false;
    label.textContent = '목소리 듣기';
  }
});
buttons.disable.addEventListener('click', async () => {
  generation++;
  buttons.disable.disabled = true;
  try {
    await request('disable');
    render('off', {title: '원래 목소리로 돌아왔어요', detail: '다시 쓰려면 새 통화 전에 연결하세요.'});
  } catch (error) {fail(error);}
  finally {buttons.disable.disabled = false;}
});

try {
  const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
  if (!tab?.id) throw Object.assign(Error(), {code: 'wrong-tab'});
  tabId = tab.id;
  const {step, page} = await request('status');
  // Opening the popup is the one-click connect, unless a connection already exists or needs attention.
  const idle = !page || !(page.ready || ['awaiting-audio-click', 'fallback'].includes(page.phase));
  if (step || idle) await connect(step || 'server');
  else showPage(page);
} catch (error) {fail(error);}
setInterval(poll, 1000);

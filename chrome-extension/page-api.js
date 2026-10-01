// Functions are serialized into the MAIN world. Keep them self-contained.
export function readStatus() {
  if (!window.__dotsTts) return null;
  const s = window.__dotsTts.status();
  return {ready: s.ready, phase: s.phase, version: s.integrationVersion,
    connection: s.connection, speaker: s.speaker, error: s.error,
    originalMuted: s.originalMuted, mode: s.backend?.mode,
    generated: s.generated, firstAudioMs: s.lastFirstAudioMs};
}

export function removeHook() {
  window.__dotsTts?.restore();
}

export async function getOffer() {
  return window.__dotsTts.getOffer();
}

export async function applyAnswer(answer) {
  await window.__dotsTts.setAnswer(answer);
  const deadline = performance.now() + 12000;
  while (performance.now() < deadline) {
    const s = window.__dotsTts.status();
    if (s.ready || (s.phase === 'awaiting-audio-click' && s.connection === 'connected')) {
      return {ready: s.ready, phase: s.phase, speaker: s.speaker,
        connection: s.connection, mode: s.backend?.mode};
    }
    if (s.error) throw Error(s.error);
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw Error('음성 연결 시간 초과. 다시 연결해 주세요.');
}

export function testVoice() {
  if (!window.__dotsTts?.status().ready) throw Error('먼저 음성을 연결하세요.');
  return Boolean(window.__dotsTts.say('안녕! 오늘은 어땠어? 편하게 이야기해 줘.'));
}

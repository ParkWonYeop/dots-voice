/* Paste into the TOP-FRAME DevTools Console BEFORE starting a NEW Chrome dot call.
   Local, in-memory test only. No recording, network calls, SDP, or track.stop(). */
(() => {
  if (window.__dotReceivePoc) {
    console.warn('PoC already installed; run __dotReceivePoc.restore() first.');
    return;
  }

  const NativePC = window.RTCPeerConnection;
  const NativeCreateElement = document.createElement;
  const NativeAudio = window.Audio;
  if (typeof NativePC !== 'function') {
    console.warn('No RTCPeerConnection in this frame; no changes made.');
    return;
  }

  let restored = false;
  let active = null;
  let pending = false;
  const timers = new Set();
  const peers = new Set();
  const audioElements = new Set();
  const report = { state: 'waiting-for-new-peer-connection', detail: '' };

  function status() {
    const result = { ...report, observedAudioElements: audioElements.size, peerConnections: peers.size };
    if (active) {
      Object.assign(result, { originalMuted: active.element.muted, detachedRenderer: !active.element.isConnected,
        trackState: active.stream.getAudioTracks()[0]?.readyState, gain: active.gain.gain.value,
        contextState: active.context.state });
      if (active.inputAnalyser) {
        const samples = new Float32Array(active.inputAnalyser.fftSize);
        active.inputAnalyser.getFloatTimeDomainData(samples);
        result.inputRms = Math.sqrt(samples.reduce((sum, x) => sum + x*x, 0) / samples.length);
        active.outputAnalyser.getFloatTimeDomainData(samples);
        result.outputRms = Math.sqrt(samples.reduce((sum, x) => sum + x*x, 0) / samples.length);
      }
    }
    return result;
  }
  function cleanupAudio() {
    if (!active) return;
    const a = active;
    active = null;
    clearInterval(a.watch);
    timers.delete(a.watch);
    // Restore original playback first, then disconnect the substitute.
    if (a.element.srcObject === a.stream)
      a.element.muted = a.originalMuted;
    try { a.source.disconnect(); a.gain.disconnect(); } catch (_) {}
    a.context.close().catch(() => {});
  }
  function restore() {
    if (restored) return;
    restored = true;
    for (const pc of peers) pc.removeEventListener('track', observeTrack);
    peers.clear();
    for (const timer of timers) clearInterval(timer);
    timers.clear();
    cleanupAudio();
    if (window.RTCPeerConnection === WrappedPC) window.RTCPeerConnection = NativePC;
    if (document.createElement === wrappedCreateElement) document.createElement = NativeCreateElement;
    if (window.Audio === WrappedAudio) window.Audio = NativeAudio;
    audioElements.clear();
    if (window.__dotReceivePoc === api) delete window.__dotReceivePoc;
    report.state = 'restored';
    report.detail = 'Original playback restored where its renderer still exists.';
    console.info('dot receive PoC restored.');
  }

  function matchingRenderer(track) {
    // Only an observed audio renderer for THIS incoming track qualifies, even when detached.
    const matches = [...audioElements].filter(el => {
      const stream = el.srcObject;
      return stream instanceof MediaStream &&
        stream.getAudioTracks().includes(track) && !el.paused &&
        !el.muted && el.volume > 0;
    });
    return matches.length === 1 ? matches[0] : null;
  }

  function observeTrack(event) {
    if (restored || active || pending || event.track.kind !== 'audio') return;
    pending = true;
    report.state = 'receive-track-seen';
    let tries = 0;
    const timer = setInterval(async () => {
      if (restored || active) { pending = false; clearInterval(timer); timers.delete(timer); return; }
      const element = matchingRenderer(event.track);
      if (!element) {
        if (++tries < 60) return;
        clearInterval(timer); timers.delete(timer);
        pending = false;
        report.state = 'failed-closed';
        report.detail = 'No unique, playing observed audio renderer linked to the receive track within 3 seconds.';
        console.warn(report.detail);
        return;
      }
      clearInterval(timer); timers.delete(timer);
      const stream = element.srcObject;
      const originalMuted = element.muted;
      let context, source, gain, inputAnalyser, outputAnalyser;
      try {
        context = new AudioContext();
        source = context.createMediaStreamSource(new MediaStream([event.track]));
        gain = context.createGain();
        gain.gain.value = 0.8;
        if (context.createAnalyser) {
          inputAnalyser = context.createAnalyser(); outputAnalyser = context.createAnalyser();
          inputAnalyser.fftSize = outputAnalyser.fftSize = 2048;
          source.connect(inputAnalyser).connect(gain).connect(outputAnalyser).connect(context.destination);
        } else source.connect(gain).connect(context.destination);
        await Promise.race([
          context.resume(),
          new Promise((_, reject) => setTimeout(() => reject(Error('AudioContext resume timed out')), 1500))
        ]);
        if (restored || context.state !== 'running' ||
            element.srcObject !== stream || !stream.getAudioTracks().includes(event.track))
          throw Error('AudioContext or original renderer is no longer ready');
        // Direct rendering is suppressed only AFTER the substitute graph runs.
        element.muted = true;
        active = { element, stream, originalMuted, context, source, gain, inputAnalyser, outputAnalyser, watch: null };
        pending = false;
        report.state = 'substitute-running';
        report.detail = 'Receive track -> GainNode(0.8) -> speakers; original DOM renderer muted.';
        console.info(report.detail, 'Run __dotReceivePoc.restore() to undo.');
        active.watch = setInterval(() => {
          if (restored || element.srcObject !== stream ||
              event.track.readyState !== 'live' || context.state !== 'running' || !element.muted) {
            cleanupAudio();
            if (!restored) { report.state = 'failed-closed'; report.detail = 'Renderer or track changed; substitute removed.'; }
          }
        }, 500);
        timers.add(active.watch);
      } catch (error) {
        pending = false;
        if (element.srcObject === stream) element.muted = originalMuted;
        try { source?.disconnect(); gain?.disconnect(); } catch (_) {}
        context?.close().catch(() => {});
        report.state = 'failed-closed';
        report.detail = String(error.message || error);
        console.warn('Substitute not enabled:', report.detail);
      }
    }, 50);
    timers.add(timer);
  }

  const WrappedPC = new Proxy(NativePC, {
    construct(target, args, newTarget) {
      const pc = Reflect.construct(target, args, newTarget);
      pc.addEventListener('track', observeTrack);
      peers.add(pc);
      report.state = 'peer-connection-seen';
      return pc;
    }
  });
  function wrappedCreateElement(...args) {
    const element = NativeCreateElement.apply(this, args);
    if (String(args[0]).toLowerCase() === 'audio') audioElements.add(element);
    return element;
  }
  const WrappedAudio = typeof NativeAudio === 'function' ? new Proxy(NativeAudio, {
    construct(target, args, newTarget) {
      const element = Reflect.construct(target, args, newTarget);
      audioElements.add(element);
      return element;
    }
  }) : NativeAudio;
  window.RTCPeerConnection = WrappedPC;
  document.createElement = wrappedCreateElement;
  if (typeof NativeAudio === 'function') window.Audio = WrappedAudio;
  const api = { status, restore, setGain(value) {
    if (!active || !Number.isFinite(value) || value < 0 || value > 1) throw Error('Active route and gain from 0 to 1 required');
    active.gain.gain.value = value;
    return status();
  }};
  window.__dotReceivePoc = api;
  console.info('PoC armed. Start a NEW dot call in this tab; check __dotReceivePoc.status().');
})();

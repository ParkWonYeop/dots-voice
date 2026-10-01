/* Run the generated runtime/install-rvc.js in top-frame Console before a NEW dot call.
   Captures only received audio; sends PCM only to the configured loopback RVC server. */
(() => {
  if (window.__dotsRvc) throw Error('Run __dotsRvc.restore() before reinstalling');
  const config = window.__dotsRvcConfig;
  if (!/^ws:\/\/127\.0\.0\.1:\d+\/voice\?token=/.test(config?.url || '')) throw Error('Loopback bridge configuration required');
  const NativePC = window.RTCPeerConnection, NativeCreate = document.createElement, NativeAudio = window.Audio;
  const elements = new Set(), peers = new Map(), intervals = new Set();
  let restored = false, active = null;
  const state = { phase: 'armed', model: config.model.model, receivedTracks: 0, sentSamples: 0,
    returnedSamples: 0, playedBlocks: 0, inputRms: 0, outputRms: 0, inferenceMs: 0,
    latencyMs: 0, maxLatencyMs: 0, flushes: 0, error: null, eventTypes: [] };
  function status() {
    return { ...state, eventTypes:[...state.eventTypes], originalMuted:active?.element.muted ?? false,
      detachedRenderer:active ? !active.element.isConnected : null,
      contextState:active?.context.state ?? null, queuedSources:active?.scheduled.size ?? 0 };
  }
  function clearScheduled(route) {
    for (const node of route.scheduled) { try { node.stop(); node.disconnect(); } catch {} }
    route.scheduled.clear(); route.nextPlay = 0;
  }
  function cleanup(error=null) {
    const route=active;active=null;
    if (route) {
      clearScheduled(route);
      if (route.element.srcObject===route.stream) route.element.muted=route.originalMuted;
      route.processor.onaudioprocess=null;
      for (const node of [route.source,route.processor,route.silent]) { try {node.disconnect();}catch{} }
      route.socket.onclose=null;route.socket.onerror=null;route.socket.onmessage=null;route.socket.close();
      route.context.close().catch(()=>{});
    }
    state.phase=error ? 'fallback' : 'stopped';state.error=error;
    console.info('DOTS_RVC_ROUTE',JSON.stringify(status()));
  }
  function flush(reason='manual') {
    if (!active) return status();
    active.epoch++;clearScheduled(active);active.captureStart=null;
    state.sentSamples=state.returnedSamples=0;state.flushes++;
    if(active.socket.readyState===WebSocket.OPEN)active.socket.send(JSON.stringify({type:'flush',epoch:active.epoch}));
    console.info('DOTS_RVC_FLUSH',reason);
    return status();
  }
  function observeEvent(event) {
    if(typeof event.data!=='string')return;
    try {
      const message=JSON.parse(event.data), types=[message.type,message.event?.type,message.response?.type].filter(Boolean);
      for (const type of types) {
        if (!state.eventTypes.includes(type))state.eventTypes.push(type);
        if (state.eventTypes.length>25)state.eventTypes.shift();
        if (/speech_started$|response\.cancelled$|output_audio_buffer\.cleared$/.test(type)) flush(type);
      }
    }catch{}
  }
  async function startRoute(element,track) {
    if (active || restored) return;
    const context=new AudioContext({sampleRate:48000});
    const source=context.createMediaStreamSource(new MediaStream([track]));
    const processor=context.createScriptProcessor(2048,1,1),silent=context.createGain();silent.gain.value=0;
    let socket;
    try {socket=new WebSocket(config.url);}catch(error){context.close();state.phase='fallback';state.error=String(error);return;}
    socket.binaryType='arraybuffer';
    const route={element,stream:element.srcObject,originalMuted:element.muted,context,source,processor,silent,socket,
      scheduled:new Set(),nextPlay:0,captureStart:null,epoch:0,opened:false};
    active=route;state.phase='connecting-bridge';
    socket.onopen=()=>{route.opened=true;socket.send(JSON.stringify({type:'config',sampleRate:context.sampleRate}));};
    socket.onerror=()=>{if(active===route)cleanup('Local bridge connection failed');};
    socket.onclose=()=>{if(active===route)cleanup('Local bridge disconnected');};
    socket.onmessage=event=>{
      if(active!==route || restored)return;
      if(typeof event.data==='string') {
        const message=JSON.parse(event.data);
        if(message.type==='ready')state.phase='bridge-ready';
        if(message.type==='metrics') {state.inferenceMs=message.inferenceMs;state.outputRms=message.outputRms;}
        if(message.type==='error')cleanup(message.message);
        return;
      }
      const packet=event.data;if(packet.byteLength<8)return;
      if(new DataView(packet).getUint32(0,true)!==route.epoch)return;
      const pcm=new Float32Array(packet,4);
      if(!pcm.every(Number.isFinite)){cleanup('Invalid converted audio');return;}
      const buffer=context.createBuffer(1,pcm.length,48000);buffer.copyToChannel(pcm,0);
      const node=context.createBufferSource();node.buffer=buffer;node.connect(context.destination);
      const start=Math.max(context.currentTime+0.04,route.nextPlay);
      if(start-context.currentTime>1){cleanup('Playback queue exceeded one second');return;}
      if(route.captureStart!==null) {
        state.latencyMs=Math.round((start-route.captureStart-state.returnedSamples/48000)*1000);
        state.maxLatencyMs=Math.max(state.maxLatencyMs,state.latencyMs);
      }
      node.onended=()=>{route.scheduled.delete(node);node.disconnect();};route.scheduled.add(node);
      element.muted=true;node.start(start);route.nextPlay=start+buffer.duration;
      state.returnedSamples+=pcm.length;state.playedBlocks++;state.phase='rvc-running';
    };
    processor.onaudioprocess=event=>{
      if(active!==route || !route.opened || socket.readyState!==WebSocket.OPEN)return;
      const pcm=event.inputBuffer.getChannelData(0);
      state.inputRms=Math.sqrt(pcm.reduce((s,x)=>s+x*x,0)/pcm.length);
      if(route.captureStart===null)route.captureStart=context.currentTime-pcm.length/48000;
      if(socket.bufferedAmount>48000*4 || state.sentSamples-state.returnedSamples>48000*3){cleanup('Inference backlog exceeded three seconds');return;}
      const packet=new ArrayBuffer(4+pcm.byteLength);new DataView(packet).setUint32(0,route.epoch,true);
      new Float32Array(packet,4).set(pcm);socket.send(packet);state.sentSamples+=pcm.length;
      event.outputBuffer.getChannelData(0).fill(0);
    };
    try {
      source.connect(processor).connect(silent).connect(context.destination);
      await context.resume();
      if(context.state!=='running')throw Error('AudioContext could not run');
    }catch(error){if(active===route)cleanup(String(error));}
  }
  function observeTrack(event) {
    if(event.track.kind!=='audio' || restored)return;
    state.receivedTracks++;
    let tries=0;
    const timer=setInterval(()=>{
      if(restored || active){clearInterval(timer);intervals.delete(timer);return;}
      const matches=[...elements].filter(el=>el.srcObject instanceof MediaStream &&
        el.srcObject.getAudioTracks().includes(event.track) && !el.paused && !el.muted && el.volume>0);
      if(matches.length===1){clearInterval(timer);intervals.delete(timer);startRoute(matches[0],event.track);}
      else if(++tries>=100){clearInterval(timer);intervals.delete(timer);state.phase='fallback';state.error='No unique received-audio renderer';}
    },50);intervals.add(timer);
  }
  const WrappedPC=new Proxy(NativePC,{construct(target,args,newTarget){
    const pc=Reflect.construct(target,args,newTarget),nativeChannel=pc.createDataChannel;
    const channels=new Set();
    const wrappedChannel=function(...parameters){const channel=nativeChannel.apply(this,parameters);channel.addEventListener('message',observeEvent);channels.add(channel);return channel;};
    pc.createDataChannel=wrappedChannel;
    const connection=()=>{if(active && (pc.connectionState==='closed'||pc.connectionState==='failed'))cleanup();};
    pc.addEventListener('track',observeTrack);pc.addEventListener('connectionstatechange',connection);
    peers.set(pc,{nativeChannel,wrappedChannel,channels,connection});return pc;
  }});
  function wrappedCreate(...args){const element=NativeCreate.apply(this,args);if(String(args[0]).toLowerCase()==='audio')elements.add(element);return element;}
  const WrappedAudio=new Proxy(NativeAudio,{construct(target,args,newTarget){const element=Reflect.construct(target,args,newTarget);elements.add(element);return element;}});
  function restore(){
    if(restored)return;restored=true;cleanup();
    for(const timer of intervals)clearInterval(timer);intervals.clear();
    for(const [pc,info] of peers){pc.removeEventListener('track',observeTrack);pc.removeEventListener('connectionstatechange',info.connection);
      if(pc.createDataChannel===info.wrappedChannel)pc.createDataChannel=info.nativeChannel;
      for(const channel of info.channels)channel.removeEventListener('message',observeEvent);}
    if(window.RTCPeerConnection===WrappedPC)window.RTCPeerConnection=NativePC;
    if(document.createElement===wrappedCreate)document.createElement=NativeCreate;
    if(window.Audio===WrappedAudio)window.Audio=NativeAudio;
    peers.clear();elements.clear();state.phase='restored';
    delete window.__dotsRvcConfig;delete window.__dotsRvc;
  }
  window.RTCPeerConnection=WrappedPC;document.createElement=wrappedCreate;window.Audio=WrappedAudio;
  window.__dotsRvc={status,flush,restore};
  console.info('DOTS_RVC_ARMED',JSON.stringify(status()));
})();

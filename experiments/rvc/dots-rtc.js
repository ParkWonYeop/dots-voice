/* Local WebRTC relay: run before a NEW dot call. No original microphone changes. */
(() => {
  if(window.__dotsRtc)throw Error('Run __dotsRtc.restore() first');
  const NativePC=window.RTCPeerConnection,NativeCreate=document.createElement,NativeAudio=window.Audio;
  const elements=new Set(),peers=new Map(),timers=new Set();
  let active=null,restored=false;
  const state={phase:'armed',model:'Yui.pth',receivedTracks:0,offerReady:false,offerFile:null,
    error:null,flushes:0,eventTypes:[],originalMuted:false,inputRms:0,outputRms:0};
  function rms(analyser){if(!analyser)return 0;const x=new Float32Array(analyser.fftSize);analyser.getFloatTimeDomainData(x);return Math.sqrt(x.reduce((s,v)=>s+v*v,0)/x.length);}
  function status(){return {...state,eventTypes:[...state.eventTypes],originalMuted:active?.element.muted??false,
    detachedRenderer:active?!active.element.isConnected:null,contextState:active?.context?.state??null,
    inputRms:rms(active?.inputAnalyser),outputRms:rms(active?.outputAnalyser),
    bridgeConnection:active?.pc.connectionState??null,backend:active?.backend??null};}
  function cleanup(error=null){
    const route=active;active=null;
    if(route){
      if(route.element.srcObject===route.originalStream)route.element.muted=route.originalMuted;
      for(const node of [route.source,route.inputSource,route.inputAnalyser,route.inputSilent,route.outputAnalyser,route.gain]){try{node?.disconnect();}catch{}}
      route.context?.close().catch(()=>{});route.pc.close();route.clone.stop();
    }
    state.phase=error?'fallback':'stopped';state.error=error;
    console.info('DOTS_RTC_ROUTE',JSON.stringify(status()));
  }
  function flush(reason='manual'){
    if(!active)return status();
    if(active.channel.readyState==='open')active.channel.send(JSON.stringify({type:'flush'}));
    if(active.gain){const gain=active.gain;gain.gain.setValueAtTime(0,active.context.currentTime);
      const timer=setTimeout(()=>{timers.delete(timer);if(active?.gain===gain)gain.gain.value=0.65;},200);timers.add(timer);}
    state.flushes++;console.info('DOTS_RTC_FLUSH',reason);return status();
  }
  function observeEvent(event){
    if(typeof event.data!=='string')return;
    try{const d=JSON.parse(event.data);for(const type of [d.type,d.event?.type,d.response?.type].filter(Boolean)){
      if(!state.eventTypes.includes(type))state.eventTypes.push(type);if(state.eventTypes.length>25)state.eventTypes.shift();
      if(/speech_started$|response\.cancelled$|output_audio_buffer\.cleared$/.test(type))flush(type);
    }}catch{}
  }
  async function startRoute(element,track){
    if(active||restored)return;
    const pc=new NativePC({iceServers:[],bundlePolicy:'max-bundle'}),clone=track.clone();
    const route={element,originalStream:element.srcObject,originalMuted:element.muted,pc,clone,
      channel:pc.createDataChannel('local-rvc-control'),backend:null,context:null,source:null};
    active=route;state.phase='gathering-local-offer';pc.addTrack(clone,new MediaStream([clone]));
    route.channel.onmessage=event=>{try{route.backend=JSON.parse(event.data);}catch{}};
    route.channel.onopen=()=>{route.channel.send(JSON.stringify({type:'status'}));};
    pc.onconnectionstatechange=()=>{if(active===route&&['failed','closed'].includes(pc.connectionState))cleanup(pc.connectionState==='failed'?'Local WebRTC connection failed':null);};
    pc.ontrack=async event=>{
      if(event.track.kind!=='audio'||active!==route)return;
      try{
        const context=new AudioContext({sampleRate:48000});route.context=context;
        route.inputSource=context.createMediaStreamSource(new MediaStream([track]));
        route.inputAnalyser=context.createAnalyser();route.inputSilent=context.createGain();route.inputSilent.gain.value=0;
        route.inputSource.connect(route.inputAnalyser).connect(route.inputSilent).connect(context.destination);
        route.source=context.createMediaStreamSource(new MediaStream([event.track]));
        route.outputAnalyser=context.createAnalyser();route.gain=context.createGain();route.gain.gain.value=0.65;
        route.source.connect(route.gain).connect(route.outputAnalyser).connect(context.destination);
        await context.resume();if(context.state!=='running')throw Error('AudioContext did not run');
        const ready=()=>{if(active!==route)return;element.muted=true;state.phase='rvc-running';console.info('DOTS_RTC_RUNNING',JSON.stringify(status()));};
        if(event.track.muted)event.track.addEventListener('unmute',ready,{once:true});else ready();
      }catch(error){cleanup(String(error));}
    };
    try{
      await pc.setLocalDescription(await pc.createOffer());
      if(pc.iceGatheringState!=='complete')await new Promise((resolve,reject)=>{
        const timeout=setTimeout(()=>reject(Error('Local ICE gathering timed out')),10000);
        pc.addEventListener('icegatheringstatechange',()=>{if(pc.iceGatheringState==='complete'){clearTimeout(timeout);resolve();}});
      });
      state.offerReady=true;state.phase='awaiting-local-answer';console.info('DOTS_RTC_OFFER_READY');
    }catch(error){cleanup(String(error));}
  }
  function observeTrack(event){
    if(restored||event.track.kind!=='audio')return;state.receivedTracks++;let attempts=0;
    const timer=setInterval(()=>{
      if(restored||active){clearInterval(timer);timers.delete(timer);return;}
      const match=[...elements].filter(e=>e.srcObject instanceof MediaStream&&e.srcObject.getAudioTracks().includes(event.track)&&!e.paused&&!e.muted&&e.volume>0);
      if(match.length===1){clearInterval(timer);timers.delete(timer);startRoute(match[0],event.track);}
      else if(++attempts>=100){clearInterval(timer);timers.delete(timer);state.phase='fallback';state.error='No unique incoming-audio renderer';}
    },50);timers.add(timer);
  }
  const WrappedPC=new Proxy(NativePC,{construct(target,args,newTarget){
    const pc=Reflect.construct(target,args,newTarget),nativeChannel=pc.createDataChannel,channels=new Set();
    const wrappedChannel=function(...args){const channel=nativeChannel.apply(this,args);channel.addEventListener('message',observeEvent);channels.add(channel);return channel;};
    pc.createDataChannel=wrappedChannel;pc.addEventListener('track',observeTrack);
    peers.set(pc,{nativeChannel,wrappedChannel,channels});return pc;
  }});
  function wrappedCreate(...args){const e=NativeCreate.apply(this,args);if(String(args[0]).toLowerCase()==='audio')elements.add(e);return e;}
  const WrappedAudio=new Proxy(NativeAudio,{construct(target,args,newTarget){const e=Reflect.construct(target,args,newTarget);elements.add(e);return e;}});
  function restore(){
    if(restored)return;restored=true;cleanup();for(const timer of timers){clearInterval(timer);clearTimeout(timer);}timers.clear();
    for(const [pc,info]of peers){pc.removeEventListener('track',observeTrack);if(pc.createDataChannel===info.wrappedChannel)pc.createDataChannel=info.nativeChannel;for(const ch of info.channels)ch.removeEventListener('message',observeEvent);}
    if(window.RTCPeerConnection===WrappedPC)window.RTCPeerConnection=NativePC;
    if(document.createElement===wrappedCreate)document.createElement=NativeCreate;if(window.Audio===WrappedAudio)window.Audio=NativeAudio;
    peers.clear();elements.clear();state.phase='restored';delete window.__dotsRtc;
  }
  window.RTCPeerConnection=WrappedPC;document.createElement=wrappedCreate;window.Audio=WrappedAudio;
  window.__dotsRtc={status,flush,restore,retry(){
    if(active)throw Error('Existing local route must be stopped first');
    state.offerReady=false;state.offerFile=null;state.error=null;
    for(const pc of peers.keys())for(const receiver of pc.getReceivers()){
      const track=receiver.track;if(track.kind!=='audio'||track.readyState!=='live')continue;
      const match=[...elements].filter(e=>e.srcObject instanceof MediaStream&&e.srcObject.getAudioTracks().includes(track)&&!e.paused&&!e.muted);
      if(match.length===1){startRoute(match[0],track);return status();}
    }
    throw Error('No live original received track');
  },async setAnswer(answer){if(!active||!state.offerReady)throw Error('Offer not ready');await active.pc.setRemoteDescription(answer);return status();},
    downloadOffer(){if(!active||!state.offerReady)throw Error('Offer not ready');
      const offer={type:active.pc.localDescription.type,sdp:active.pc.localDescription.sdp};
      const url=URL.createObjectURL(new Blob([JSON.stringify(offer)],{type:'application/json'}));
      const a=NativeCreate.call(document,'a');state.offerFile='dot-loopback-offer-'+Date.now()+'.json';a.href=url;a.download=state.offerFile;a.click();
      setTimeout(()=>URL.revokeObjectURL(url),1000);return {file:state.offerFile};},
    async stats(){if(!active)return status();const stats=await active.pc.getStats();return {...status(),rtp:[...stats.values()].filter(s=>s.type==='inbound-rtp'||s.type==='outbound-rtp').map(s=>({type:s.type,kind:s.kind,bytesReceived:s.bytesReceived,bytesSent:s.bytesSent,packetsReceived:s.packetsReceived,totalAudioEnergy:s.totalAudioEnergy,totalSamplesDuration:s.totalSamplesDuration,jitter:s.jitter}))};},
    backendStatus(){if(active?.channel.readyState==='open')active.channel.send(JSON.stringify({type:'status'}));return status();}
  };
  const watch=setInterval(()=>{if(active&&(active.element.srcObject!==active.originalStream||active.clone.readyState==='ended'))cleanup();},100);timers.add(watch);
  console.info('DOTS_RTC_ARMED',JSON.stringify(status()));
})();

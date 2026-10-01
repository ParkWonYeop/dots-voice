/* Install runtime/install-tts.js before a NEW dot call, then connect the local peer. */
(() => {
  if(window.__dotsTts)throw Error('Run __dotsTts.restore() first');
  const NativePC=window.RTCPeerConnection,NativeCreate=document.createElement,NativeAudio=window.Audio;
  const Buffer=window.DotTranscriptBuffer,elements=new Set(),peers=new Map(),timers=new Set();
  let restored=false,renderer=null,originalStream=null,originalMuted=false,cloudTrack=null,serial=0;
  let firstCaptionAt=null,captionStarted=false;
  const mutedProperty=Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype,'muted');
  let muteLock=null;
  const route={pc:new NativePC({iceServers:[],bundlePolicy:'max-bundle'}),context:null,track:null,channel:null,backend:null};
  const state={integrationVersion:1,phase:'gathering-local-offer',ready:false,offerReady:false,error:null,textJobs:0,generated:0,
    flushes:0,eventTypes:[],speaker:null,style:null,lastFirstAudioMs:null};
  function rms(){if(!route.analyser)return 0;const x=new Float32Array(route.analyser.fftSize);route.analyser.getFloatTimeDomainData(x);return Math.sqrt(x.reduce((s,v)=>s+v*v,0)/x.length);}
  function status(){return {...state,eventTypes:[...state.eventTypes],originalMuted:renderer?.muted??false,
    detachedRenderer:renderer?!renderer.isConnected:null,contextState:route.context?.state??null,
    connection:route.pc.connectionState,outputRms:rms(),backend:route.backend};}
  function lockOriginal(){
    if(!renderer)return;
    if(!muteLock){
      const element=renderer;muteLock={element,own:Object.getOwnPropertyDescriptor(element,'muted'),requested:element.muted};
      Object.defineProperty(element,'muted',{configurable:true,
        get(){return mutedProperty.get.call(this);},
        set(value){muteLock.requested=Boolean(value);mutedProperty.set.call(this,state.ready?true:value);}});
    }
    mutedProperty.set.call(renderer,true);
  }
  function unmuteOriginal(){
    if(!muteLock)return;
    const lock=muteLock;muteLock=null;
    if(lock.own)Object.defineProperty(lock.element,'muted',lock.own);else delete lock.element.muted;
    if(lock.element.srcObject===originalStream)mutedProperty.set.call(lock.element,lock.requested);
  }
  function fallback(error){
    state.ready=false;state.phase='fallback';state.error=String(error);unmuteOriginal();
    route.pc.close();route.track?.stop();route.context?.close().catch(()=>{});
    console.warn('DOTS_TTS_FALLBACK',JSON.stringify(status()));
  }
  function activateAudio(){
    if(route.context?.state==='suspended')route.context.resume().then(ready).catch(fallback);
  }
  function ready(){
    if(restored||state.phase==='fallback'||!route.backend||route.context?.state!=='running'||route.pc.connectionState!=='connected')return;
    state.ready=true;state.style=route.backend.style;state.speaker=route.backend.speaker;state.phase=renderer?'tts-running':'tts-ready';
    if(renderer)lockOriginal();
  }
  function speak(text){
    if(!state.ready||route.channel.readyState!=='open')return false;
    const id='tts'+Date.now()+String(++serial);
    if(firstCaptionAt!==null&&!captionStarted){
      state.lastCaptionWaitMs=Math.round(performance.now()-firstCaptionAt);captionStarted=true;
    }
    route.channel.send(JSON.stringify({type:'speak',id,text}));state.textJobs++;state.lastText=text;return id;
  }
  function cancel(){
    if(route.channel?.readyState==='open')route.channel.send(JSON.stringify({type:'flush'}));
    if(route.gain){const gain=route.gain;gain.gain.value=0;const timer=setTimeout(()=>{timers.delete(timer);if(state.ready)gain.gain.value=1;},150);timers.add(timer);}
    state.flushes++;
  }
  const transcript=new Buffer(speak,cancel);
  function observeMessage(event){
    if(restored||typeof event.data!=='string')return;
    try{const d=JSON.parse(event.data);if(!state.eventTypes.includes(d.type))state.eventTypes.push(d.type);
      if(state.eventTypes.length>30)state.eventTypes.shift();
      if(d.type==='input_transcript.added'){firstCaptionAt=null;captionStarted=false;}
      if(d.type==='output_transcript.added'&&firstCaptionAt===null)firstCaptionAt=performance.now();
      if(state.ready)transcript.consume(d);
      if(d.type==='turn.done'&&d.turn?.role==='assistant'){firstCaptionAt=null;captionStarted=false;}
    }catch(error){console.warn('DOTS_TTS_EVENT_ERROR',String(error));}
  }
  function observeTrack(event){
    if(event.track.kind!=='audio'||restored)return;
    let attempts=0;
    const timer=setInterval(()=>{
      if(restored){clearInterval(timer);timers.delete(timer);return;}
      const matches=[...elements].filter(e=>e.srcObject instanceof MediaStream&&e.srcObject.getAudioTracks().includes(event.track)&&!e.paused&&e.volume>0);
      if(matches.length===1){
        clearInterval(timer);timers.delete(timer);unmuteOriginal();renderer=matches[0];cloudTrack=event.track;
        originalStream=renderer.srcObject;originalMuted=renderer.muted;ready();
        console.info('DOTS_TTS_RENDERER',JSON.stringify(status()));
      }else if(++attempts>=100){clearInterval(timer);timers.delete(timer);fallback('No unique incoming-audio renderer');}
    },50);timers.add(timer);
  }
  const WrappedPC=new Proxy(NativePC,{construct(target,args,newTarget){
    const pc=Reflect.construct(target,args,newTarget),nativeChannel=pc.createDataChannel,channels=new Set();
    const wrappedChannel=function(...args){const ch=nativeChannel.apply(this,args);ch.addEventListener('message',observeMessage);channels.add(ch);return ch;};
    pc.createDataChannel=wrappedChannel;pc.addEventListener('track',observeTrack);peers.set(pc,{nativeChannel,wrappedChannel,channels});return pc;
  }});
  function wrappedCreate(...args){const e=NativeCreate.apply(this,args);if(String(args[0]).toLowerCase()==='audio')elements.add(e);return e;}
  const WrappedAudio=new Proxy(NativeAudio,{construct(target,args,newTarget){const e=Reflect.construct(target,args,newTarget);elements.add(e);return e;}});
  window.RTCPeerConnection=WrappedPC;document.createElement=wrappedCreate;window.Audio=WrappedAudio;
  route.pc.addTransceiver('audio',{direction:'recvonly'});route.channel=route.pc.createDataChannel('local-tts-control');
  route.channel.onopen=()=>route.channel.send(JSON.stringify({type:'status'}));
  route.channel.onmessage=event=>{
    try{const d=JSON.parse(event.data);
      if(d.type==='metrics'){route.backend=d;ready();}
      else if(d.type==='generated'){state.generated++;state.lastGeneration=d;}
      else if(d.type==='audio_started'){state.lastFirstAudioMs=d.firstAudioMs;state.lastQueueMs=d.queueMs;}
      else if(d.type==='error')fallback(d.message);
    }catch(error){fallback(error);}
  };
  route.pc.onconnectionstatechange=()=>{
    if(restored)return;
    if(['failed','closed'].includes(route.pc.connectionState)&&state.phase!=='fallback')fallback('Local TTS peer '+route.pc.connectionState);
    else ready();
  };
  route.pc.ontrack=async event=>{
    if(event.track.kind!=='audio'||restored)return;
    try{
      route.track=event.track;route.context=new AudioContext({sampleRate:48000});
      route.source=route.context.createMediaStreamSource(new MediaStream([event.track]));
      route.gain=route.context.createGain();route.analyser=route.context.createAnalyser();route.gain.gain.value=1;
      route.source.connect(route.gain).connect(route.analyser).connect(route.context.destination);
      route.context.addEventListener('statechange',ready);
      if(route.context.state==='suspended')state.phase='awaiting-audio-click';
      activateAudio();ready();
    }catch(error){if(!restored)fallback(error);}
  };
  function restore(){
    if(restored)return;restored=true;cancel();unmuteOriginal();state.ready=false;
    for(const timer of timers){clearTimeout(timer);clearInterval(timer);}timers.clear();
    route.pc.close();route.track?.stop();route.context?.close().catch(()=>{});
    for(const [pc,info]of peers){pc.removeEventListener('track',observeTrack);if(pc.createDataChannel===info.wrappedChannel)pc.createDataChannel=info.nativeChannel;for(const ch of info.channels)ch.removeEventListener('message',observeMessage);}
    if(window.RTCPeerConnection===WrappedPC)window.RTCPeerConnection=NativePC;
    if(document.createElement===wrappedCreate)document.createElement=NativeCreate;
    if(window.Audio===WrappedAudio)window.Audio=NativeAudio;
    window.removeEventListener('pointerdown',activateAudio,true);
    window.removeEventListener('keydown',activateAudio,true);
    if(window.DotTranscriptBuffer===Buffer)delete window.DotTranscriptBuffer;
    state.phase='restored';delete window.__dotsTts;console.info('DOTS_TTS_RESTORED');
  }
  window.__dotsTts={status,say:speak,flush(){transcript.interrupt();return status();},restore,
    async getOffer(){
      const deadline=performance.now()+12000;
      while(!state.offerReady){
        if(restored||state.phase==='fallback')throw Error(state.error||'Voice hook was removed');
        if(performance.now()>deadline)throw Error('Local offer timed out');
        await new Promise(resolve=>setTimeout(resolve,50));
      }
      return {type:route.pc.localDescription.type,sdp:route.pc.localDescription.sdp};
    },
    async setAnswer(answer){await route.pc.setRemoteDescription(answer);return status();},
    downloadOffer(){if(!state.offerReady)throw Error('Offer not ready');const a=NativeCreate.call(document,'a');
      const u=URL.createObjectURL(new Blob([JSON.stringify(route.pc.localDescription)],{type:'application/json'}));
      const file='dots-tts-offer-'+Date.now()+'.json';a.href=u;a.download=file;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);return {file};},
    async stats(){const s=await route.pc.getStats();return {...status(),rtp:[...s.values()].filter(x=>x.type==='inbound-rtp').map(x=>({bytes:x.bytesReceived,packets:x.packetsReceived,jitter:x.jitter}))};},
    backendStatus(){if(route.channel.readyState==='open')route.channel.send(JSON.stringify({type:'status'}));return status();}
  };
  window.addEventListener('pointerdown',activateAudio,true);
  window.addEventListener('keydown',activateAudio,true);
  const watch=setInterval(()=>{
    if(renderer&&(renderer.srcObject!==originalStream||cloudTrack.readyState==='ended')){
      cancel();unmuteOriginal();renderer=null;cloudTrack=null;state.phase=state.ready?'tts-ready':state.phase;
    }
    if(state.ready&&route.context.state!=='running')fallback('TTS audio context stopped');
  },100);timers.add(watch);
  (async()=>{
    try{await route.pc.setLocalDescription(await route.pc.createOffer());
      if(route.pc.iceGatheringState!=='complete')await new Promise((resolve,reject)=>{
        const timer=setTimeout(()=>reject(Error('Local ICE gathering timed out')),10000);
        route.pc.addEventListener('icegatheringstatechange',()=>{if(route.pc.iceGatheringState==='complete'){clearTimeout(timer);resolve();}});
      });
      if(restored)return;state.offerReady=true;state.phase='awaiting-local-answer';console.info('DOTS_TTS_OFFER_READY');
    }catch(error){if(!restored)fallback(error);}
  })();
})();

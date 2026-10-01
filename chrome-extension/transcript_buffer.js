/* GPT-Live's observed word transcripts -> assistant-only TTS phrases. */
(function (root) {
  class DotTranscriptBuffer {
    constructor(say, cancel, options={}) {
      this.say=say;this.cancel=cancel;this.ids=new Set();this.cancelled=new Set();
      this.minChars=options.minChars??18;this.maxChars=options.maxChars??140;
      this.firstMinChars=options.firstMinChars??8;this.emitted=false;
      this.pending='';this.received='';this.turn=null;this.userSpeaking=false;this.drop=false;this.waiting=[];
    }
    flushText(final=false) {
      // Start at the first useful sentence; keep later phrases longer for flow.
      while(this.pending.length>=(this.emitted?this.minChars:this.firstMinChars)){
        const endings=[...this.pending.matchAll(/[.!?。！？](?=\s|$)/gu)].map(m=>m.index+m[0].length);
        const minimum=this.emitted?this.minChars:this.firstMinChars;
        let end=endings.filter(n=>n>=minimum&&n<=this.maxChars).pop();
        if(!end&&this.pending.length>this.maxChars){
          end=endings.filter(n=>n<=this.maxChars).pop()||this.pending.lastIndexOf(' ',this.maxChars);
          if(end<=20)end=this.maxChars;
        }
        if(!end)break;
        this.say(this.pending.slice(0,end).trim());this.emitted=true;this.pending=this.pending.slice(end);
      }
      if(final){const text=this.pending.trim();this.pending='';if(text)this.say(text);}
    }
    append(text){if(typeof text!=='string'||!text)return;this.received+=text;this.pending+=text;this.flushText();}
    interrupt() {
      if(this.turn)this.cancelled.add(this.turn);
      this.pending='';this.received='';this.waiting=[];this.emitted=false;this.drop=true;this.cancel();
    }
    consume(event) {
      if(event.type==='input_transcript.added'){
        if(!this.userSpeaking){this.userSpeaking=true;this.interrupt();}return;
      }
      if(event.type==='output_transcript.added'){
        const item=event.item||{};
        if(item.id&&this.ids.has(item.id))return;
        if(item.id){this.ids.add(item.id);if(this.ids.size>1000)this.ids.delete(this.ids.values().next().value);}
        if(this.drop){this.waiting.push(event);if(this.waiting.length>50)this.waiting.shift();}
        else this.append(item.text);return;
      }
      const turn=event.turn;
      if(event.type==='turn.created'&&turn?.role==='assistant'){
        this.turn=turn.id;
        if(this.drop||!this.received){
          const initial=turn.transcript||'';
          const candidates=this.waiting.filter(e=>typeof turn.start_ms!=='number'||e.end_ms>=turn.start_ms);
          let text=candidates.map(e=>e.item?.text||'').join('');
          // Output words can arrive before turn.created; recover all of that prefix.
          if(!text.startsWith(initial))text=initial;
          this.waiting=[];this.drop=false;this.append(text);
        }return;
      }
      if(event.type==='turn.done'&&turn?.role==='user'){this.userSpeaking=false;return;}
      if(event.type==='turn.done'&&turn?.role==='assistant'){
        if(this.cancelled.has(turn.id)){this.cancelled.delete(turn.id);return;}
        const full=turn.transcript||'';
        if(!this.drop&&full.startsWith(this.received))this.append(full.slice(this.received.length));
        if(!this.drop)this.flushText(true);
        this.received='';this.pending='';this.turn=null;this.emitted=false;
      }
    }
  }
  if(typeof module==='object'&&module.exports)module.exports=DotTranscriptBuffer;
  else root.DotTranscriptBuffer=DotTranscriptBuffer;
})(typeof window==='object'?window:this);

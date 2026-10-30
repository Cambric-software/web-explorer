// Themes keep the original palette and fonts. Ambient audio never autoplays.
(function(root){
  const THEMES=['original','index','terminal'],SOUNDS=['rain','drift'];
  function normalize(value){const v=value&&typeof value==='object'?value:{};return {
    theme:THEMES.includes(v.theme)?v.theme:'original',chill:v.chill===true,
    sound:SOUNDS.includes(v.sound)?v.sound:'rain',volume:Number.isFinite(v.volume)?Math.max(0,Math.min(100,v.volume)):25};}
  const rules={normalize};if(typeof module!=='undefined')module.exports=rules;
  if(typeof document==='undefined')return;
  const $=s=>document.querySelector(s);
  let prefs=normalize(store.get('lounge',{})),ctx=null,bus=null,nodes=[],playing=false,generation=0;
  function save(){store.set('lounge',prefs)}
  function paint(){document.documentElement.dataset.theme=prefs.theme;document.body.classList.toggle('chill',prefs.chill);
    $('#setting-theme').value=prefs.theme;$('#setting-chill').checked=prefs.chill;$('#setting-ambient').value=prefs.sound;
    $('#setting-volume').value=prefs.volume;$('#ambient-volume').textContent=prefs.volume+'%';
    $('#ambient-play').textContent=playing?'■ Stop':'▶ Play';$('#ambient-play').setAttribute('aria-pressed',String(playing));
    $('#ambient-state').textContent=playing?'Playing · '+(prefs.sound==='rain'?'Soft rain':'Slow drift'):'Paused';}
  function stop(){generation++;playing=false;for(const n of nodes){try{n.stop()}catch{}}nodes=[];
    if(bus){bus.disconnect();bus=null}if(ctx)ctx.suspend().catch(()=>{});paint();}
  async function play(){stop();const ticket=generation;try{
    const Audio=root.AudioContext||root.webkitAudioContext;if(!Audio)throw Error('unavailable');
    ctx=ctx||new Audio();await ctx.resume();if(ticket!==generation)return;
    bus=ctx.createGain();bus.gain.setValueAtTime(0,ctx.currentTime);bus.gain.linearRampToValueAtTime(prefs.volume/100*.16,ctx.currentTime+1);bus.connect(ctx.destination);
    if(prefs.sound==='rain'){
      const buffer=ctx.createBuffer(1,ctx.sampleRate*6,ctx.sampleRate),samples=buffer.getChannelData(0);let last=0;
      for(let i=0;i<samples.length;i++){last=(last+Math.random()*.04-.02)/1.02;samples[i]=last*5;}
      const source=ctx.createBufferSource(),filter=ctx.createBiquadFilter();source.buffer=buffer;source.loop=true;filter.type='lowpass';filter.frequency.value=1100;
      source.connect(filter).connect(bus);source.start();nodes.push(source);
    }else{
      for(const freq of [130.81,196,261.63]){const o=ctx.createOscillator(),g=ctx.createGain();o.type='sine';o.frequency.value=freq;g.gain.value=.18;o.connect(g).connect(bus);o.start();nodes.push(o);}
      const lfo=ctx.createOscillator(),depth=ctx.createGain();lfo.frequency.value=.08;depth.gain.value=1.5;lfo.connect(depth).connect(nodes[0].frequency);lfo.start();nodes.push(lfo);
    }
    playing=true;paint();
  }catch{stop();notice('Ambient sound is unavailable in this browser.');}}
  $('#setting-theme').onchange=e=>{prefs.theme=e.target.value;save();paint()};
  $('#setting-chill').onchange=e=>{prefs.chill=e.target.checked;save();paint()};
  $('#setting-ambient').onchange=e=>{prefs.sound=e.target.value;save();if(playing)play();else paint()};
  $('#setting-volume').oninput=e=>{prefs.volume=Number(e.target.value);save();if(bus&&ctx)bus.gain.setTargetAtTime(prefs.volume/100*.16,ctx.currentTime,.1);paint()};
  $('#ambient-play').onclick=()=>playing?stop():play();
  document.addEventListener('visibilitychange',()=>{if(document.hidden&&playing)stop()});
  root.addEventListener('pagehide',stop);root.addEventListener('hashchange',paint);
  paint();
})(typeof window==='undefined'?globalThis:window);

// Arcade Mode sound effects + Explorer Passport & Badges.
// Sounds are generated in the browser (no audio files, nothing downloaded). Off by default.
// Uses app.js globals: SITES, ALL, store, esc, history, favs, votes, lists, notice, C.
(function(){
  const $=s=>document.querySelector(s);
  // ---------------- Arcade sounds
  let on=store.get('sound',false),ctx=null;
  function tone(freq,dur,type='square',when=0,vol=.06){if(!on)return;try{ctx=ctx||new (window.AudioContext||window.webkitAudioContext)();
    const t=ctx.currentTime+when,o=ctx.createOscillator(),g=ctx.createGain();o.type=type;o.frequency.setValueAtTime(freq,t);
    g.gain.setValueAtTime(vol,t);g.gain.exponentialRampToValueAtTime(.0001,t+dur);o.connect(g).connect(ctx.destination);o.start(t);o.stop(t+dur+.02)}catch{}}
  const SFX={
    explore:()=>{tone(440,.08);tone(660,.08,'square',.07);tone(880,.12,'square',.14)},
    like:()=>{tone(660,.08,'triangle');tone(990,.12,'triangle',.07)},
    gem:()=>{[784,988,1175,1568].forEach((f,i)=>tone(f,.12,'triangle',i*.06))},
    down:()=>{tone(300,.12,'sawtooth',0,.04);tone(200,.18,'sawtooth',.1,.04)},
    save:()=>{tone(523,.08,'square');tone(784,.14,'square',.08)},
    badge:()=>{[523,659,784,1047,784,1047].forEach((f,i)=>tone(f,.14,'square',i*.09,.05))},
    click:()=>tone(1200,.03,'square',0,.03)};
  window.sfx=n=>SFX[n]&&SFX[n]();
  document.addEventListener('click',e=>{if(!on)return;const b=e.target.closest('button,a.btn,[data-act]');if(!b)return;
    const a=b.dataset.act,id=b.id;
    if(id==='go'||id==='stumble-go'||id==='sb-next'||id==='galaxy-random')SFX.explore();
    else if(a==='up')SFX.like();else if(a==='gem'||id==='sb-gem')SFX.gem();else if(a==='down')SFX.down();
    else if(a==='fav'||id==='sb-save'||a==='list')SFX.save();else SFX.click()},true);
  function soundUi(){const box=$('#setting-sound');if(!box)return;box.checked=on;box.onchange=()=>{on=box.checked;store.set('sound',on);if(on)SFX.badge()}}
  // ---------------- Passport & badges
  function stats(){const seen=[...new Set(history)],bySite=new Map(ALL.map(s=>[s.url,s])),vis=seen.map(u=>bySite.get(u)).filter(Boolean);
    const cats=new Set(vis.map(s=>s.category)),years=vis.map(s=>Number(s.first_seen)).filter(y=>y>0),langs=new Set(vis.map(s=>s.lang).filter(l=>l&&l!=='?'));
    const v=Object.values(votes);return {explored:seen.length,cats:cats.size,catList:[...cats].sort(),favs:favs.length,likes:v.filter(x=>x===1).length,gems:v.filter(x=>x===3).length,
      voted:v.filter(x=>x).length,lists:lists.length,oldest:years.length?Math.min(...years):0,langs:langs.size,trails:store.get('trails_done',0),
      dead:vis.filter(s=>s.status==='dead').length}}
  const BADGES=[
    ['first','👣','First Steps','Explore your first website',s=>s.explored>=1],
    ['ten','🧭','Wanderer','Explore 10 websites',s=>s.explored>=10],
    ['fifty','🗺','Cartographer','Explore 50 websites',s=>s.explored>=50],
    ['hundred','🚀','Deep Space','Explore 100 websites',s=>s.explored>=100],
    ['cats5','🎨','Well-Rounded','Visit 5 different categories',s=>s.cats>=5],
    ['cats10','🌈','Renaissance','Visit 10 different categories',s=>s.cats>=10],
    ['gem','💎','Gem Hunter','Mark a hidden gem',s=>s.gems>=1],
    ['gems10','👑','Treasure Keeper','Mark 10 hidden gems',s=>s.gems>=10],
    ['critic','🗳','Critic','Vote on 25 websites',s=>s.voted>=25],
    ['fav','⭐','Collector','Save 5 favorites',s=>s.favs>=5],
    ['list','📚','Curator','Create a list',s=>s.lists>=1],
    ['old','📼','Time Traveller','Visit a website archived before 2000',s=>s.oldest>0&&s.oldest<2000],
    ['google','🦖','Before Google','Visit a website archived before 1998',s=>s.oldest>0&&s.oldest<1998],
    ['langs','🌍','Polyglot','Visit websites in 3 languages',s=>s.langs>=3],
    ['trail','🥾','Trailblazer','Finish a Vibe Journey',s=>s.trails>=1],
    ['trails','🏔','Pathfinder','Finish 5 Vibe Journeys',s=>s.trails>=5]];
  let earned=store.get('badges',{});
  function check(quiet){if(!ALL.length)return;const s=stats();let fresh=[];
    for(const [id,icon,name,,test] of BADGES)if(!earned[id]&&test(s)){earned[id]=new Date().toISOString().slice(0,10);fresh.push(icon+' '+name)}
    if(fresh.length){store.set('badges',earned);if(!quiet){notice('🏅 Badge unlocked: '+fresh.join(', '));SFX.badge()}}}
  function render(){check(true);const s=stats(),r=C.rank(s.explored),n=Object.keys(earned).length;
    $('#passport').innerHTML=`<div class="passport-card"><div class="passport-head"><div><span class="kicker">Explorer passport</span><h3>${esc(r.name)}</h3>
      <p class="muted">${r.next?`${r.next-s.explored} more websites to the next rank`:'Highest rank reached!'}</p><progress max="100" value="${r.progress}"></progress></div>
      <div class="passport-seal">${n}<span>of ${BADGES.length} badges</span></div></div>
      <div class="stats">${[[s.explored,'websites explored'],[s.cats,'categories visited'],[s.favs,'favorites'],[s.gems,'hidden gems'],[s.voted,'votes cast'],[s.lists,'lists'],[s.trails,'journeys finished'],[s.oldest||'—','oldest archive year']].map(([v,l])=>`<div><b>${esc(v)}</b>${l}</div>`).join('')}</div>
      ${s.catList.length?`<p class="muted">Stamps: ${s.catList.map(c=>`<span class="tag">${esc(c)}</span>`).join(' ')}</p>`:''}</div>
      <h3>Badges</h3><div class="badges">${BADGES.map(([id,icon,name,how])=>`<div class="badge ${earned[id]?'got':''}" title="${esc(how)}"><span class="badge-icon">${earned[id]?icon:'🔒'}</span><b>${esc(name)}</b><span class="muted">${earned[id]?'Earned '+esc(earned[id]):esc(how)}</span></div>`).join('')}</div>
      <p class="muted">Your passport lives only in this browser. Badges are re-earned automatically from your exported data.</p>`}
  document.addEventListener('click',()=>setTimeout(()=>check(false),50));
  window.addEventListener('hashchange',()=>{if(location.hash==='#passport')render();if(location.hash==='#settings')soundUi()});
  const ready=setInterval(()=>{if(!ALL.length&&!document.querySelector('#go')?.disabled)return;clearInterval(ready);soundUi();check(true);if(location.hash==='#passport')render()},150);
})();

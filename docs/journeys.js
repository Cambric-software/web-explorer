// Time Warp Slider (1994–2026) and Vibe Journeys & Curated Trails.
// Uses app.js globals: SITES, store, esc, dom, card, stumble, notice, current, C.
(function(){
  const $=s=>document.querySelector(s),NOW=2026,MIN=1994;
  // ---------------- Time Warp
  const eraOf=y=>y>=2014?'':y<=1999?'era-90s':y<=2006?'era-y2k':'era-web2';
  const eraName=y=>y>=NOW?'Now — normal look':y<=1999?'Web 1.0 · '+y:y<=2006?'Y2K web · '+y:y<=2013?'Web 2.0 · '+y:'Modern web · '+y;
  function setWarp(y,save=true){y=Math.max(MIN,Math.min(NOW,+y||NOW));window.WARP=y>=NOW?0:y;
    const root=document.documentElement;root.classList.remove('era-90s','era-y2k','era-web2');const e=eraOf(y);if(e)root.classList.add(e);
    $('#warp').value=y;$('#warp-label').textContent=eraName(y);
    const n=SITES.filter(s=>!window.WARP||(Number(s.first_seen)>0&&Number(s.first_seen)<=window.WARP)).length;
    $('#warp-count').textContent=window.WARP?`${n} websites already existed in ${y}`:'';
    if(save)store.set('warp',y);seen.clear()}
  $('#warp').oninput=e=>setWarp(e.target.value);
  $('#warp-reset').onclick=()=>setWarp(NOW);
  // ---------------- Vibe Journeys
  function seeded(seed){let n=0;for(const c of seed)n=(n*31+c.charCodeAt(0))>>>0;return()=>{n=(n*1664525+1013904223)>>>0;return n/4294967296}}
  function shuffle(arr,seed){const r=seeded(seed),a=[...arr];for(let i=a.length-1;i>0;i--){const j=Math.floor(r()*(i+1));[a[i],a[j]]=[a[j],a[i]]}return a}
  const week=(()=>{const d=new Date(),y=new Date(Date.UTC(d.getUTCFullYear(),0,1));return d.getUTCFullYear()+'-w'+Math.ceil(((d-y)/864e5+y.getUTCDay()+1)/7)})();
  const TRAILS=[
    {id:'small-web',name:'Small Web Wander',vibe:'Cozy personal homepages and old-web corners.',icon:'🌿',pick:s=>['Personal','Retro'].includes(s.category)},
    {id:'makers',name:"Maker's Bench",vibe:'Gadgets, handy tools and things people built.',icon:'🛠',pick:s=>['Technology','Tools','Developer'].includes(s.category)},
    {id:'curious',name:'Curious Minds',vibe:'Science, history and learning something new.',icon:'🔭',pick:s=>['Science','Education'].includes(s.category)},
    {id:'play',name:'Play & Make',vibe:'Games, art and music for a break.',icon:'🎨',pick:s=>['Games','Art'].includes(s.category)},
    {id:'capsule',name:'Time Capsule',vibe:'The oldest websites in the collection, oldest first.',icon:'⏳',pick:s=>Number(s.first_seen)>0,order:a=>a.sort((x,y)=>x.first_seen-y.first_seen)},
    {id:'fresh',name:'Fresh Off the Robot',vibe:'The very newest discoveries.',icon:'🤖',pick:()=>true,order:a=>a.sort((x,y)=>(y.added||'').localeCompare(x.added||''))},
    {id:'wildcard',name:'Wildcard Trail',vibe:'Unsortable, surprising, a little strange.',icon:'🎲',pick:s=>['Random','Communities','News'].includes(s.category)}];
  const STOPS=8;
  function stops(t){let a=SITES.filter(t.pick);a=t.order?t.order(a):shuffle(a.sort((x,y)=>x.url.localeCompare(y.url)),week+t.id);return a.slice(0,STOPS)}
  let progress=store.get('journeys',{}),J=null;
  function renderJourneys(){const html=TRAILS.map(t=>{const s=stops(t);if(s.length<3)return '';const p=progress[t.id+'@'+week]||0,done=p>=s.length;
    return `<article class="site trail"><div class="site-body"><span class="tag">${t.icon} ${s.length} stops</span><h3>${esc(t.name)}</h3><p>${esc(t.vibe)}</p>
    <ol class="stops">${s.map((x,i)=>`<li class="${i<p?'done':''}">${esc(x.title)} <span class="muted">${esc(dom(x.url))}</span></li>`).join('')}</ol>
    <progress max="${s.length}" value="${p}"></progress><div class="inline"><button class="sb-next" data-trail="${t.id}">${done?'↺ Walk again':p?'Continue → stop '+(p+1):'Start the trail →'}</button>${done?'<span class="tag">✓ Completed</span>':''}</div></div></article>`}).join('');
    $('#trails').innerHTML=html||'<p class="muted">Trails appear once the robot has found enough websites. Check back soon!</p>'}
  function step(){const s=J.stops[J.i];stumble(s);$('#sb-dom').textContent=`${J.t.icon} ${J.t.name} · stop ${J.i+1} of ${J.stops.length} · ${dom(s.url)}`;
    $('#sb-next').textContent=J.i+1<J.stops.length?'NEXT STOP →':'FINISH ✓'}
  function startTrail(id){const t=TRAILS.find(x=>x.id===id),s=stops(t);if(!s.length)return;const k=t.id+'@'+week;let i=progress[k]||0;if(i>=s.length)i=0;J={t,stops:s,i,k};step()}
  document.addEventListener('click',e=>{const b=e.target.closest('[data-trail]');if(b)startTrail(b.dataset.trail)});
  // The Stumble Bar's NEXT button walks the trail while a journey is active
  const next=$('#sb-next');next.onclick=null;
  next.addEventListener('click',()=>{if(!J){explore();stumble(current);return}
    J.i++;progress[J.k]=J.i;store.set('journeys',progress);
    if(J.i>=J.stops.length){notice(`🎉 You finished “${J.t.name}”!`);J=null;$('#sb-close').click();return}step()});
  $('#sb-close').addEventListener('click',()=>{J=null;$('#sb-next').textContent='NEXT →';if(location.hash==='#journeys')renderJourneys()});
  window.addEventListener('hashchange',()=>{if(location.hash==='#journeys')renderJourneys()});
  // Wait for the website data, then restore the warp and paint the trails
  const ready=setInterval(()=>{if(!SITES.length&&!document.querySelector('#go')?.disabled)return;clearInterval(ready);setWarp(store.get('warp',NOW),false);if(location.hash==='#journeys')renderJourneys()},150);
})();

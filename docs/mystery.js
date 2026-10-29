// Daily Mystery Challenge & Calendar + Vibe Check / Tech Tag filters.
// The mystery website is the same for every visitor on a given day (picked from the date).
// Progress lives only in this browser (localStorage key we_mystery).
// Uses app.js globals: SITES, ALL, store, esc, dom, card, notice, browse, stumble, C.
(function(){
  const $=s=>document.querySelector(s),MAX=5;
  let book=store.get('mystery',{}),day=today();
  function today(){return new Date().toISOString().slice(0,10)}
  function seed(str){let n=2166136261;for(const c of str)n=Math.imul(n^c.charCodeAt(0),16777619)>>>0;return n}
  function pool(){return SITES.filter(s=>s.title&&s.description&&s.review!=='flagged')}
  function secret(d){const p=[...pool()].sort((a,b)=>a.url.localeCompare(b.url));return p.length?p[seed('mystery:'+d)%p.length]:null}
  function choices(d,s){const p=pool().filter(x=>x.url!==s.url&&x.title!==s.title),out=[s],used=new Set([s.title]);let n=seed('choices:'+d);
    while(out.length<4&&used.size<p.length+1){n=Math.imul(n,1103515245)+12345>>>0;const x=p[n%p.length];if(!used.has(x.title)){used.add(x.title);out.push(x)}}
    return out.sort((a,b)=>seed(d+a.url)-seed(d+b.url))}
  function mask(s){const words=s.title.toLowerCase().split(/\W+/).filter(w=>w.length>2);let t=s.description;
    for(const w of words)t=t.replace(new RegExp('\\b'+w.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'\\b','gi'),'▒▒▒');return t}
  function clues(s){return [
    ['Category',s.category],
    ['Vibe',(s.vibes||[]).join(', ')||'no strong vibe'],
    ['Built with',(s.tech||[]).join(', ')||'unknown tools'],
    ['First archived',s.first_seen?String(s.first_seen):'not in the archive yet'],
    ['Description',mask(s)]]}
  function state(d){return book[d]||(book[d]={clues:1,wrong:[],done:false,won:false})}
  function save(){store.set('mystery',book)}
  function points(st){return st.won?Math.max(1,MAX+1-st.clues):0}
  function streak(){let n=0,d=new Date(day+'T00:00:00Z');for(;;){const k=d.toISOString().slice(0,10);if(!book[k]?.won)break;n++;d.setUTCDate(d.getUTCDate()-1)}return n}
  function render(){const box=$('#mystery');if(!box)return;const s=secret(day);if(!s){box.innerHTML='<p class="muted">Waiting for websites…</p>';return}
    const st=state(day),opts=choices(day,s),cl=clues(s),label=day===today()?"Today's mystery":'Mystery of '+new Date(day+'T00:00:00Z').toLocaleDateString(undefined,{timeZone:'UTC'});
    box.innerHTML=`<div class="mystery"><p class="kicker">${esc(label)} · streak ${streak()} 🔥 · ${Object.values(book).reduce((a,x)=>a+points(x),0)} total points</p>
      <ol class="clues">${cl.map((c,i)=>i<(st.done?MAX:st.clues)?`<li><b>${esc(c[0])}:</b> ${esc(c[1])}</li>`:`<li class="locked">🔒 Clue ${i+1}</li>`).join('')}</ol>
      ${st.done?`<p class="result">${st.won?`🎉 Solved with ${st.clues} clue${st.clues>1?'s':''} — ${points(st)} points!`:'😶 Not this time. Here it is:'}</p>${card(s)}`:
      `<div class="choices">${opts.map(o=>`<button data-guess="${esc(o.url)}" ${st.wrong.includes(o.url)?'disabled class="wrong"':''}>${esc(o.title)}<small>${esc(dom(o.url))}</small></button>`).join('')}</div>
      <div class="inline"><button id="m-clue" ${st.clues>=MAX?'disabled':''}>🔍 Reveal next clue (−1 point)</button><button id="m-give">Give up</button></div>`}</div>`;
    calendar()}
  function calendar(){const el=$('#mystery-cal');if(!el)return;const t=today(),d=new Date(day+'T00:00:00Z'),y=d.getUTCFullYear(),m=d.getUTCMonth();
    const first=new Date(Date.UTC(y,m,1)),days=new Date(Date.UTC(y,m+1,0)).getUTCDate(),lead=(first.getUTCDay()+6)%7;let cells='';
    for(let i=0;i<lead;i++)cells+='<span></span>';
    for(let i=1;i<=days;i++){const k=`${y}-${String(m+1).padStart(2,'0')}-${String(i).padStart(2,'0')}`,b=book[k],fut=k>t;
      const cls=fut?'future':b?.won?'won':b?.done?'lost':b?'started':'missed';
      cells+=`<button data-day="${k}" class="${cls}${k===day?' on':''}" ${fut?'disabled':''} aria-label="${k}: ${cls}">${i}${b?.won?'<small>★'+points(b)+'</small>':''}</button>`}
    el.innerHTML=`<div class="cal-head"><button data-month="-1" aria-label="Previous month">‹</button><b>${first.toLocaleDateString(undefined,{month:'long',year:'numeric',timeZone:'UTC'})}</b><button data-month="1" aria-label="Next month" ${`${y}-${String(m+1).padStart(2,'0')}`>=t.slice(0,7)?'disabled':''}>›</button></div>
      <div class="cal">${['Mo','Tu','We','Th','Fr','Sa','Su'].map(x=>`<i>${x}</i>`).join('')}${cells}</div>
      <p class="muted">★ solved · ✕ missed guess · empty days can still be played. Every past day keeps its own mystery.</p>`}
  document.addEventListener('click',e=>{const g=e.target.closest('[data-guess]'),dd=e.target.closest('[data-day]'),mo=e.target.closest('[data-month]');
    if(g){const st=state(day),s=secret(day);if(st.done)return;
      if(g.dataset.guess===s.url){st.done=st.won=true;window.sfx?.('badge');notice('Correct! 🎉')}
      else{st.wrong.push(g.dataset.guess);window.sfx?.('down');if(st.clues<MAX)st.clues++;else st.done=true;if(st.wrong.length>=3)st.done=true}
      save();render();return}
    if(e.target.closest('#m-clue')){const st=state(day);if(st.clues<MAX){st.clues++;save();render()}return}
    if(e.target.closest('#m-give')){const st=state(day);st.done=true;st.clues=MAX;save();render();return}
    if(dd){day=dd.dataset.day;render();return}
    if(mo){const d=new Date(day+'T00:00:00Z');d.setUTCDate(1);d.setUTCMonth(d.getUTCMonth()+Number(mo.dataset.month));let k=d.toISOString().slice(0,10);if(k>today())k=today();day=k;render()}});
  window.addEventListener('hashchange',()=>{if(location.hash==='#mystery'){day=today();render()}});
  // Vibe + tech filter menus in Browse
  function fillFilters(){const count=(f)=>{const m={};SITES.forEach(s=>(s[f]||[]).forEach(v=>m[v]=(m[v]||0)+1));return Object.entries(m).sort((a,b)=>b[1]-a[1])};
    for(const [id,f] of [['#vibe','vibes'],['#tech','tech']]){const el=$(id);if(!el)continue;const keep=el.value;
      el.innerHTML=el.options[0].outerHTML+count(f).map(([v,n])=>`<option value="${esc(v)}">${esc(v)} (${n})</option>`).join('');el.value=keep;el.onchange=()=>browse()}}
  window.mysteryToday=()=>secret(today());
  const ready=setInterval(()=>{if(!SITES.length)return;clearInterval(ready);fillFilters();if(location.hash==='#mystery')render()},150);
})();

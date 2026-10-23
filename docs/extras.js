// Extra interactions: secret door, swipe to explore, category counts, surprise category, empty state.
(function(){
  const $=s=>document.querySelector(s);
  // Secret door: click the logo 5 times quickly, or type "cambric" anywhere.
  let clicks=0,timer,typed='';
  $('.logo')?.addEventListener('click',()=>{clicks++;clearTimeout(timer);timer=setTimeout(()=>clicks=0,1500);if(clicks>=5)location.href='admin.html'});
  document.addEventListener('keydown',e=>{if(e.target.closest?.('input,textarea,select'))return;typed=(typed+e.key.toLowerCase()).slice(-7);if(typed==='cambric')location.href='admin.html'});
  // Swipe left on the card to explore the next website (phones)
  let x0=null;const card=$('#card');
  card?.addEventListener('touchstart',e=>x0=e.touches[0].clientX,{passive:true});
  card?.addEventListener('touchend',e=>{if(x0===null)return;const dx=e.changedTouches[0].clientX-x0;x0=null;if(Math.abs(dx)>70)$('#go').click()});
  // Little launch animation on Explore
  $('#go')?.addEventListener('click',()=>{if(document.documentElement.dataset.motion==='off')return;card.classList.remove('pop');void card.offsetWidth;card.classList.add('pop')});
  // Surprise category button
  const go=$('#go');if(go){const b=document.createElement('button');b.type='button';b.className='ghost';b.textContent='🎲 Surprise category';b.title='Pick a random category and explore (R)';
    b.onclick=()=>{const opts=[...$('#cat').options].slice(1);if(!opts.length)return;const o=opts[Math.floor(Math.random()*opts.length)];$('#cat').value=o.value;$('#cat').dispatchEvent(new Event('change'));go.click()};
    go.after(b);document.addEventListener('keydown',e=>{if((e.key==='r'||e.key==='R')&&!e.target.closest('input,textarea,select')&&!e.ctrlKey&&!e.metaKey)b.click()})}
  // Category counts on browse chips + empty-state message
  fetch('data/sites.json').then(r=>r.json()).then(d=>{const alive=d.sites.filter(s=>s.status!=='dead');const n={};alive.forEach(s=>n[s.category]=(n[s.category]||0)+1);
    const paint=()=>document.querySelectorAll('#chips [data-c]').forEach(b=>{if(b.dataset.counted)return;b.dataset.counted=1;b.insertAdjacentHTML('beforeend',` <small>${b.dataset.c?n[b.dataset.c]||0:alive.length}</small>`)});
    paint();new MutationObserver(paint).observe($('#chips'),{childList:true});
    if(!alive.length){$('#card').innerHTML='<p class="muted">🤖 The robot is rebuilding the collection from scratch. Fresh, correctly sorted websites arrive every 3 hours — check back soon!</p>';$('#go').disabled=true}}).catch(()=>{});
})();

// ---- Taste DNA: a 16-axis radar of the visitor's long-term taste, with sliders to tune it by hand (stays in this browser).
(()=>{const AX=['Tools','Play','Audio','Visual art','Knowledge','Personal','Interactive','Long visits','Dense visuals','Retro','Quirky','Mobile','Embeddable','Handmade','Sound on','Evergreen'];
 const N=AX.length,root=document.getElementById('dna');if(!root||typeof REC==='undefined'||!REC.getLong)return;
 const R=120,C=160,pt=(i,r)=>{const a=-Math.PI/2+i*2*Math.PI/N;return[C+Math.cos(a)*r,C+Math.sin(a)*r]};
 function svg(v){let g='';for(const f of[.25,.5,.75,1])g+=`<polygon class="ring" points="${AX.map((_,i)=>pt(i,R*f).join(',')).join(' ')}"/>`;
  AX.forEach((n,i)=>{const[x,y]=pt(i,R),[tx,ty]=pt(i,R+22);g+=`<line class="spoke" x1="${C}" y1="${C}" x2="${x}" y2="${y}"/><text x="${tx}" y="${ty}" text-anchor="middle" dominant-baseline="middle">${n}</text>`});
  g+=`<polygon class="shape" points="${v.map((x,i)=>pt(i,R*x).join(',')).join(' ')}"/>`;
  return`<svg class="dna-svg" viewBox="-40 -6 400 332" role="img" aria-label="Your taste DNA radar">${g}</svg>`}
 function top(v){return v.map((x,i)=>[x,AX[i]]).sort((a,b)=>b[0]-a[0]).slice(0,3).map(([,n])=>`<span>${n}</span>`).join('')}
 function render(){const v=REC.getLong();root.innerHTML=`<div class="dna-card"><div class="kicker">Taste DNA</div><h3 style="margin:4px 0">What you like, at a glance</h3><p class="muted">Learned from your likes, skips and time spent. Drag a slider to steer what Explore shows you next.</p><div class="dna-top">${top(v)}</div><div class="dna-wrap"><div id="dna-chart">${svg(v)}</div><div><div class="dna-sliders">${AX.map((n,i)=>`<label><b>${n}<em>${Math.round(v[i]*100)}</em></b><input type="range" min="0" max="100" value="${Math.round(v[i]*100)}" data-i="${i}" aria-label="${n}"></label>`).join('')}</div><p><button type="button" id="dna-reset">⟲ Reset to neutral</button></p></div></div></div>`;
  root.querySelectorAll('input[type=range]').forEach(el=>el.oninput=()=>{const w=REC.getLong();w[+el.dataset.i]=el.value/100;REC.setLong(w);el.previousElementSibling.querySelector('em').textContent=el.value;root.querySelector('#dna-chart').innerHTML=svg(w);root.querySelector('.dna-top').innerHTML=top(w)});
  root.querySelector('#dna-reset').onclick=()=>{REC.setLong(Array(N).fill(.5));render()}}
 const go=()=>{if(location.hash==='#passport')render()};addEventListener('hashchange',go);go()})();

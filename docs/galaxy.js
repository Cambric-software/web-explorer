// 2D Interactive Galaxy Star Map + Living Webring Constellation Graph + Global Top 25 Hall of Fame.
// Uses app.js globals: SITES, votes, favs, history, esc, dom, stumble, notice.
(function(){
  const $=s=>document.querySelector(s);
  // ---------------- Galaxy
  const cv=$('#galaxy-canvas'),ctx=cv.getContext('2d'),tip=$('#galaxy-tip');
  let stars=[],clusters=[],links=[],view={x:0,y:0,z:1},drag=null,hover=null,raf=0,spread=60,showLines=true;
  const css=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  function hash(s){let n=2166136261;for(const c of s)n=Math.imul(n^c.charCodeAt(0),16777619)>>>0;return n}
  function cosine(a,b){if(!a||!b||!a.length||!b.length)return 0;let d=0,ma=0,mb=0;for(let i=0;i<Math.min(a.length,b.length);i++){d+=a[i]*b[i];ma+=a[i]*a[i];mb+=b[i]*b[i]}return ma&&mb?d/(Math.sqrt(ma)*Math.sqrt(mb)):0}

  function build(){
    const cats=[...new Set(SITES.map(s=>s.category))].sort(),R=Math.max(260,cats.length*38);spread=40+Math.sqrt(SITES.length)*6;
    clusters=cats.map((c,i)=>{const a=i/cats.length*Math.PI*2;return {c,x:Math.cos(a)*R,y:Math.sin(a)*R,n:0}});
    stars=SITES.map(s=>{
      const cl=clusters.find(k=>k.c===s.category);cl.n++;
      const h=hash(s.url),a=(h%3600)/3600*Math.PI*2,d=Math.sqrt(((h>>>12)%1000)/1000)*spread;
      const score=(votes[s.url]||0)+(favs.includes(s.url)?5:0);
      return {s,x:cl.x+Math.cos(a)*d,y:cl.y+Math.sin(a)*d,r:1.8+Math.min(4.2,Math.max(0,score)*.6)+(Number(s.first_seen)&&s.first_seen<2005?1.2:0),tw:(h%100)/100,neighbors:[]};
    });

    // Build Webring & Cosine Constellation links
    const linkSet=new Set();links=[];
    for(let i=0;i<stars.length;i++){
      const p=stars[i],scored=[];
      for(let j=0;j<stars.length;j++){
        if(i===j)continue;
        const q=stars[j];
        const sim=cosine(p.s.vector,q.s.vector);
        const pTags=new Set([...(p.s.tags||[]),...(p.s.vibes||[])].map(t=>t.toLowerCase()));
        const qTags=[...(q.s.tags||[]),...(q.s.vibes||[])].map(t=>t.toLowerCase());
        const shared=qTags.filter(t=>pTags.has(t)).length;
        const weight=sim*0.75+Math.min(0.25,shared*0.08);
        if(weight>0.60)scored.push({target:q,weight,sim,shared});
      }
      scored.sort((a,b)=>b.weight-a.weight);
      for(const cand of scored.slice(0,3)){
        const u1=p.s.url,u2=cand.target.s.url,key=u1<u2?u1+'|'+u2:u2+'|'+u1;
        if(!linkSet.has(key)){
          linkSet.add(key);
          const linkObj={a:p,b:cand.target,weight:cand.weight,sim:cand.sim,shared:cand.shared};
          links.push(linkObj);
          p.neighbors.push({star:cand.target,sim:cand.sim});
          cand.target.neighbors.push({star:p,sim:cand.sim});
        }
      }
    }
  }

  function fit(){
    const w=cv.clientWidth,h=cv.clientHeight,dpr=devicePixelRatio||1;cv.width=w*dpr;cv.height=h*dpr;ctx.setTransform(dpr,0,0,dpr,0,0);
    if(!stars.length)return;
    const xs=stars.map(p=>p.x),ys=stars.map(p=>p.y),span=Math.max(Math.max(...xs)-Math.min(...xs),Math.max(...ys)-Math.min(...ys))+220;
    view={x:0,y:0,z:Math.min(w,h)/span};
  }

  const toScreen=p=>[(p.x-view.x)*view.z+cv.clientWidth/2,(p.y-view.y)*view.z+cv.clientHeight/2];

  function draw(now){
    raf=0;if($('#v-galaxy').hidden)return;
    const w=cv.clientWidth,h=cv.clientHeight,fg=css('--fg'),acc=css('--acc'),mu=css('--muted');
    ctx.clearRect(0,0,w,h);

    // Draw Constellation threads
    if(showLines&&links.length){
      for(const link of links){
        const isHover=hover&&(link.a===hover||link.b===hover);
        const [x1,y1]=toScreen(link.a),[x2,y2]=toScreen(link.b);
        if((x1<0&&x2<0)||(x1>w&&x2>w)||(y1<0&&y2<0)||(y1>h&&y2>h))continue;

        ctx.beginPath();
        ctx.moveTo(x1,y1);
        ctx.lineTo(x2,y2);

        if(isHover){
          ctx.strokeStyle=acc;
          ctx.lineWidth=Math.max(1.5,2*Math.sqrt(view.z));
          ctx.globalAlpha=0.85;
          ctx.stroke();

          // Animated energy pulse along constellation line
          const pulse=((now/1100)%1);
          const px=x1+(x2-x1)*pulse,py=y1+(y2-y1)*pulse;
          ctx.fillStyle=acc;
          ctx.beginPath();
          ctx.arc(px,py,3,0,7);
          ctx.fill();
        } else {
          ctx.strokeStyle=mu;
          ctx.lineWidth=Math.max(0.6,1*Math.sqrt(view.z));
          ctx.globalAlpha=Math.min(0.28,link.weight*0.25*Math.max(0.4,Math.sqrt(view.z)));
          ctx.stroke();
        }
      }
    }

    // Cluster titles
    ctx.font='600 13px "Space Grotesk",sans-serif';ctx.textAlign='center';
    for(const k of clusters){const [x,y]=toScreen(k);ctx.fillStyle=mu;ctx.globalAlpha=0.7;ctx.fillText(`${k.c.toUpperCase()} · ${k.n}`,x,y-spread*view.z-12)}

    // Stars
    const been=new Set(history),still=document.body.classList.contains('no-motion');
    const hoverNeighbors=hover?new Set(hover.neighbors.map(n=>n.star)):new Set();

    for(const p of stars){
      const [x,y]=toScreen(p);
      if(x<-10||y<-10||x>w+10||y>h+10)continue;
      const tw=still?1:.65+.35*Math.sin(now/700+p.tw*6.28),r=p.r*Math.max(.8,Math.sqrt(view.z));
      const isHov=p===hover,isNeighbor=hoverNeighbors.has(p);

      ctx.globalAlpha=isHov?1:(isNeighbor?0.95:tw);
      ctx.fillStyle=isHov||isNeighbor||(votes[p.s.url]||0)>0||favs.includes(p.s.url)?acc:fg;
      ctx.beginPath();
      ctx.arc(x,y,isHov?r*1.5:(isNeighbor?r*1.2:r),0,7);
      ctx.fill();

      if(isHov||isNeighbor){
        ctx.strokeStyle=acc;
        ctx.lineWidth=isHov?2:1;
        ctx.globalAlpha=isHov?0.7:0.4;
        ctx.beginPath();
        ctx.arc(x,y,r+5,0,7);
        ctx.stroke();
      }

      if(been.has(p.s.url)&&!isHov){
        ctx.globalAlpha=.45;
        ctx.strokeStyle=acc;
        ctx.lineWidth=1;
        ctx.beginPath();
        ctx.arc(x,y,r+3,0,7);
        ctx.stroke();
      }
    }
    ctx.globalAlpha=1;raf=requestAnimationFrame(draw);
  }

  function pick(e){
    const b=cv.getBoundingClientRect(),mx=e.clientX-b.left,my=e.clientY-b.top;let best=null,bd=16*16;
    for(const p of stars){const [x,y]=toScreen(p),d=(x-mx)**2+(y-my)**2;if(d<bd){bd=d;best=p}}return best;
  }

  cv.addEventListener('pointerdown',e=>{drag={x:e.clientX,y:e.clientY,vx:view.x,vy:view.y,moved:false};cv.setPointerCapture(e.pointerId)});
  cv.addEventListener('pointermove',e=>{
    if(drag){
      const dx=e.clientX-drag.x,dy=e.clientY-drag.y;
      if(Math.abs(dx)+Math.abs(dy)>4)drag.moved=true;
      view.x=drag.vx-dx/view.z;view.y=drag.vy-dy/view.z;
      return;
    }
    hover=pick(e);cv.style.cursor=hover?'pointer':'grab';
    if(hover){
      const b=cv.getBoundingClientRect();tip.hidden=false;tip.style.left=(e.clientX-b.left+14)+'px';tip.style.top=(e.clientY-b.top+14)+'px';
      const nList=hover.neighbors.slice(0,2).map(n=>`${esc(dom(n.star.s.url))} (${Math.round(n.sim*100)}%)`).join(', ');
      const webringText=nList?`<div class="galaxy-webring" style="margin-top:4px;font-size:11px;opacity:0.85;color:var(--acc)">🕸 Constellation: ${nList}</div>`:'';
      tip.innerHTML=`<b>${esc(hover.s.title)}</b><br><span>${esc(dom(hover.s.url))} · ${esc(hover.s.category)}</span>${webringText}`;
    }else tip.hidden=true;
  });
  cv.addEventListener('pointerup',e=>{const was=drag;drag=null;if(was&&!was.moved){const p=pick(e);if(p)stumble(p.s)}});
  cv.addEventListener('wheel',e=>{e.preventDefault();view.z=Math.min(12,Math.max(.15,view.z*Math.exp(-e.deltaY*.0015)))},{passive:false});
  $('#galaxy-zoom-in').onclick=()=>view.z=Math.min(12,view.z*1.4);$('#galaxy-zoom-out').onclick=()=>view.z=Math.max(.15,view.z/1.4);$('#galaxy-reset').onclick=fit;
  $('#galaxy-random').onclick=()=>{if(!stars.length)return;const p=stars[Math.floor(Math.random()*stars.length)];view={x:p.x,y:p.y,z:4};hover=p;setTimeout(()=>stumble(p.s),600)};

  const linesBtn=$('#galaxy-lines');
  if(linesBtn){
    linesBtn.onclick=()=>{
      showLines=!showLines;
      linesBtn.textContent=showLines?'🕸 Constellations: ON':'🕸 Constellations: OFF';
      linesBtn.setAttribute('aria-pressed',showLines);
    };
  }

  function openGalaxy(){
    build();fit();
    $('#galaxy-count').textContent=`${stars.length} stars in ${clusters.length} constellations with ${links.length} living webring links. Drag to fly, scroll to zoom, click a star to visit. Green stars are ones you liked; rings are ones you\'ve seen.`;
    if(!raf)raf=requestAnimationFrame(draw);
  }
  addEventListener('resize',()=>{if(!$('#v-galaxy').hidden)fit()});

  // ---------------- Hall of Fame
  let GLOBAL=null;
  const mine=()=>{const m={};for(const s of SITES){const n=(votes[s.url]||0)+(favs.includes(s.url)?5:0);if(n)m[s.url]=n}return m};
  async function openFame(){if(!GLOBAL){try{GLOBAL=await (await fetch('data/votes.json?t='+Date.now())).json()}catch{GLOBAL={voters:0,sites:{}}}}
    const tab=$('#fame-tab').value,src=tab==='mine'?Object.fromEntries(Object.entries(mine()).map(([u,n])=>[u,{score:n,voters:1}])):GLOBAL.sites;
    const rows=SITES.filter(s=>src[s.url]&&src[s.url].score>0).sort((a,b)=>src[b.url].score-src[a.url].score||src[b.url].voters-src[a.url].voters).slice(0,25);
    $('#fame-note').textContent=tab==='mine'?'Your own top websites, from your likes, gems and favorites in this browser.':`Totals from ${GLOBAL.voters||0} explorers. Your likes and gems count automatically — no account needed. Updated every hour.`;
    $('#fame').innerHTML=rows.map((s,i)=>`<li class="fame-row"><span class="fame-rank">${i<3?['🥇','🥈','🥉'][i]:'#'+(i+1)}</span><div class="fame-info"><b>${esc(s.title)}</b><span class="muted">${esc(dom(s.url))} · ${esc(dom(s.url))} · ${esc(s.category)}</span></div><span class="fame-score">${src[s.url].score} pts${tab==='mine'?'':' · '+src[s.url].voters+' voters'}</span><button data-act="stumble" data-u="${esc(s.url)}" aria-label="Preview ${esc(s.title)}">▣</button></li>`).join('')
      ||`<p class="muted">${tab==='mine'?'Like, gem or favorite some websites and they will rank here.':'No shared votes yet. Be the first — press “Share my votes”.'}</p>`}
  $('#fame-tab').onchange=openFame;
  $('#fame-share').onclick=()=>{const lines=Object.entries(mine()).sort((a,b)=>b[1]-a[1]).slice(0,200).map(([u,n])=>(n>0?'+':'')+n+' '+u);
    if(!lines.length){notice('Vote on some websites first.');return}
    const body=`My Website Explorer votes (one vote set per GitHub account; sending again replaces it).\n\n${lines.join('\n')}`.slice(0,7000);
    window.open('https://github.com/Cambric-software/web-explorer/issues/new?'+new URLSearchParams({title:'Votes: '+lines.length+' websites',body}),'_blank','noopener')};
  function route(){if(location.hash==='#galaxy')openGalaxy();if(location.hash==='#fame')openFame()}
  addEventListener('hashchange',route);
  const ready=setInterval(()=>{if(!SITES.length&&!$('#go')?.disabled)return;clearInterval(ready);route()},150);
})();

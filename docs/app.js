const $=s=>document.querySelector(s);let SITES=[],STATS={},cat="",seen=new Set();
const store={get:(k,d)=>JSON.parse(localStorage.getItem("we_"+k)||JSON.stringify(d)),set:(k,v)=>localStorage.setItem("we_"+k,JSON.stringify(v))};
let favs=store.get("favs",[]),votes=store.get("votes",{});
const esc=s=>String(s||"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const dom=u=>{try{return new URL(u).hostname.replace(/^www\./,"")}catch{return u}};
function card(s){const f=favs.includes(s.url),v=votes[s.url]||0;
 return `<div class="site"><span class="tag">${esc(s.category)}</span><h3>${esc(s.title)}</h3><div class="dom">${esc(dom(s.url))}</div>
 <p>${esc(s.description)||'<span class="muted">No description.</span>'}</p><div class="acts"><a class="visit" href="${esc(s.url)}" target="_blank" rel="noopener">Visit ↗</a>
 <button data-act="up" data-u="${esc(s.url)}" class="${v>0?"on":""}">▲</button><button data-act="down" data-u="${esc(s.url)}" class="${v<0?"on":""}">▼</button>
 <button data-act="fav" data-u="${esc(s.url)}" class="${f?"on":""}">${f?"★ Saved":"☆ Save"}</button></div></div>`}
function explore(){let pool=SITES.filter(s=>(!cat||s.category===cat)&&!seen.has(s.url)&&(votes[s.url]||0)>=0);
 if(!pool.length){seen.clear();pool=SITES.filter(s=>!cat||s.category===cat)}
 const s=pool[Math.floor(Math.random()*pool.length)];if(!s)return;seen.add(s.url);
 const h=store.get("history",[]);store.set("history",[s.url,...h].slice(0,200));$("#card").innerHTML=card(s)}
function browse(){const q=$("#q").value.toLowerCase(),c=$("#chips .on")?.dataset.c||"";
 const r=SITES.filter(s=>(!c||s.category===c)&&(!q||(s.title+s.description+s.url).toLowerCase().includes(q)));
 $("#list").innerHTML=r.slice(0,120).map(card).join("")||'<p class="muted">Nothing found.</p>'}
function renderFavs(){$("#favs").innerHTML=SITES.filter(s=>favs.includes(s.url)).map(card).join("")||'<p class="muted">No favorites yet — hit ☆ Save on a site.</p>'}
function renderStats(){const cats={};SITES.forEach(s=>cats[s.category]=(cats[s.category]||0)+1);
 $("#statbox").innerHTML=`<div class="stats"><div><b>${SITES.length}</b>verified websites</div><div><b>${STATS.found_last_run||0}</b>found last run</div>
 <div><b>${STATS.runs||0}</b>discovery runs</div><div><b>${Object.keys(cats).length}</b>categories</div><div><b>${store.get("history",[]).length}</b>sites you explored</div></div>
 <p class="muted">Last run: ${STATS.last_run?new Date(STATS.last_run).toLocaleString():"not yet"}</p>
 <p>${Object.entries(cats).sort((a,b)=>b[1]-a[1]).map(([k,n])=>`<span class="tag">${esc(k)} ${n}</span>`).join(" ")}</p>`}
document.addEventListener("click",e=>{const b=e.target.closest("[data-act]");if(!b)return;const u=b.dataset.u,a=b.dataset.act;
 if(a==="fav"){favs=favs.includes(u)?favs.filter(x=>x!==u):[...favs,u];store.set("favs",favs)}
 else{const n=a==="up"?1:-1;votes[u]=votes[u]===n?0:n;store.set("votes",votes)}
 b.closest(".site").outerHTML=card(SITES.find(s=>s.url===u));if(location.hash==="#favorites")renderFavs()});
function route(){const v=(location.hash||"#explore").slice(1);document.querySelectorAll(".view").forEach(x=>x.hidden=x.id!=="v-"+v);
 document.querySelectorAll("nav a").forEach(a=>a.classList.toggle("on",a.hash==="#"+v));if(v==="browse")browse();if(v==="favorites")renderFavs();if(v==="stats")renderStats()}
Promise.all([fetch("data/sites.json").then(r=>r.json()),fetch("data/stats.json").then(r=>r.json())]).then(([d,s])=>{SITES=d.sites.filter(x=>x.status!=="dead");STATS=s;
 const cats=[...new Set(SITES.map(x=>x.category))].sort();$("#cat").innerHTML+=cats.map(c=>`<option>${esc(c)}</option>`).join("");
 $("#chips").innerHTML='<button class="on" data-c="">All</button>'+cats.map(c=>`<button data-c="${esc(c)}">${esc(c)}</button>`).join("");route()});
$("#go").onclick=explore;$("#cat").onchange=e=>{cat=e.target.value;seen.clear()};$("#q").oninput=browse;
$("#chips").onclick=e=>{if(e.target.dataset.c===undefined)return;$("#chips .on")?.classList.remove("on");e.target.classList.add("on");browse()};
window.onhashchange=route;

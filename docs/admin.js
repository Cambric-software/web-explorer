// Control Room Pro: visual moderation queue for the website database with Brick, Block, & Bot Schedule controls.
const REPO='Cambric-software/web-explorer',PATH='docs/data/sites.json',BLOCKED_PATH='docs/data/blocked.json',BOT_CFG_PATH='docs/data/bot-config.json',BRICK_PATH='docs/data/brick.json',$=s=>document.querySelector(s);
const CATS=['Art','Business','Communities','Developer','Education','Games','News','Personal','Retro','Science','Technology','Tools','Random'];
const REVIEW={unreviewed:'Unreviewed',verified:'Verified safe',flagged:'Flagged'};
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const PASS_HASH='dccf9ce19cd40e7d364d73482805b53667d1e494d2078c3952bda34a5a84e7c4',VAULT='data/admin-key.json';
let token='',db=null,sha='',shown=60;
let edits={},deleted=new Set(),added=[],wiped=false,selected=new Set(),pendingBlocks=new Set();
let botCfg={paused:false,interval_hours:1},botCfgSha='';
const dirty=()=>Object.keys(edits).length+deleted.size+added.length+(wiped?1:0)+pendingBlocks.size;
const hostKey=u=>{try{return new URL(u).hostname.toLowerCase().replace(/\.$/,'').replace(/^(www\d?|m|mobile|amp)\.(?=.+\..+)/,'')}catch{return ''}};
const gh=async(path,opt={})=>{const r=await fetch('https://api.github.com'+path,{...opt,headers:{Authorization:'Bearer '+token,Accept:'application/vnd.github+json',...(opt.headers||{})}});if(!r.ok&&r.status!==204)throw Error(r.status+' '+(await r.text()).slice(0,120));return r.status===204?null:r.json()};
const msg=t=>$('#msg').textContent=t;
const fromB64=s=>new TextDecoder().decode(Uint8Array.from(atob(s.replace(/\n/g,'')),c=>c.charCodeAt(0)));
function enc(str){const b=new TextEncoder().encode(str);let out='';for(let i=0;i<b.length;i+=0x8000)out+=String.fromCharCode(...b.subarray(i,i+0x8000));return btoa(out)}

async function unlock(){
  const repo=await gh('/repos/'+REPO);if(!repo.permissions?.push)throw Error('This account cannot edit the project.');
  const me=await gh('/user').catch(()=>({login:'owner'}));$('#who').textContent='Signed in as '+me.login;
  $('#login').hidden=true;$('#panel').hidden=false;await load();runs();await loadBotConfig();
}
async function fetchDb(){const f=await gh(`/repos/${REPO}/contents/${PATH}?ref=main`);
  const raw=f.content?fromB64(f.content):await (await fetch(f.download_url+'?t='+Date.now())).text();return {sha:f.sha,data:JSON.parse(raw)}}
async function load(){const r=await fetchDb();sha=r.sha;db=r.data;edits={};deleted=new Set();added=[];wiped=false;selected.clear();pendingBlocks.clear();render()}
function replay(base){
  if(wiped){
    // Immunity: keep only bricked sites on wipe
    base.sites=base.sites.filter(s=>s.brick===true);
    base.beta_start=db.beta_start;
  }
  base.sites=base.sites.filter(s=>!deleted.has(s.url));
  for(const s of base.sites)if(edits[s.url])Object.assign(s,edits[s.url]);
  const have=new Set(base.sites.map(s=>hostKey(s.url)));base.sites.unshift(...added.filter(s=>!have.has(hostKey(s.url))));return base}

async function save(){
  msg('Saving changes to GitHub…');
  try{
    const latest=await fetchDb();const next=replay(latest.data);
    await gh(`/repos/${REPO}/contents/${PATH}`,{method:'PUT',body:JSON.stringify({message:`Control room: ${dirty()} change(s)`,sha:latest.sha,content:enc(JSON.stringify(next,null,1)),branch:'main'})});
    
    // Save updated brick.json registry
    try{
      const bricked=next.sites.filter(s=>s.brick===true).map(s=>({url:s.url,title:s.title,category:s.category,added:s.added}));
      const oldBrick=await gh(`/repos/${REPO}/contents/${BRICK_PATH}?ref=main`).catch(()=>null);
      await gh(`/repos/${REPO}/contents/${BRICK_PATH}`,{method:'PUT',body:JSON.stringify({message:'Control room: sync brick immunity registry',content:enc(JSON.stringify({updated:new Date().toISOString().slice(0,10),total_bricked:bricked.length,sites:bricked},null,2)),branch:'main',...(oldBrick?{sha:oldBrick.sha}:{})})});
    }catch(err){console.warn('Could not sync brick.json:',err)}

    // If any domains were permanently blocked, update blocked.json
    if(pendingBlocks.size>0){
      try{
        const oldBlk=await gh(`/repos/${REPO}/contents/${BLOCKED_PATH}?ref=main`).catch(()=>null);
        let blkData={updated:new Date().toISOString().slice(0,10),total_blocked:0,domains:[],entries:[]};
        if(oldBlk&&oldBlk.content){
          const parsed=JSON.parse(fromB64(oldBlk.content));
          if(Array.isArray(parsed))blkData.domains=parsed;
          else if(parsed&&parsed.domains)blkData=parsed;
        }
        const domSet=new Set(blkData.domains||[]);
        for(const d of pendingBlocks){
          if(!domSet.has(d)){
            domSet.add(d);
            blkData.entries.unshift({domain:d,blocked_at:new Date().toISOString().slice(0,10),reason:'control_room_manual_block'});
          }
        }
        blkData.domains=Array.from(domSet).sort();
        blkData.total_blocked=blkData.domains.length;
        blkData.updated=new Date().toISOString().slice(0,10);
        await gh(`/repos/${REPO}/contents/${BLOCKED_PATH}`,{method:'PUT',body:JSON.stringify({message:`Control room: block ${pendingBlocks.size} domain(s)`,content:enc(JSON.stringify(blkData,null,2)),branch:'main',...(oldBlk?{sha:oldBlk.sha}:{})})});
      }catch(err){console.warn('Could not update blocked.json:',err)}
    }

    msg('Saved successfully! The live catalog will update in about a minute.');await load();
  }catch(e){msg('Could not save: '+e.message)}
}

async function runs(){try{const r=await gh(`/repos/${REPO}/actions/workflows/discover.yml/runs?per_page=6`);
  $('#runs').innerHTML=r.workflow_runs.map(x=>`${new Date(x.created_at).toLocaleString()} — ${esc(x.conclusion||x.status)} <a href="${esc(x.html_url)}" target="_blank" rel="noopener">details ↗</a>`).join('<br>')||'No runs yet.'}catch{$('#runs').textContent='Run history unavailable (token needs Actions: read).'}}

// Bot Config controls
async function loadBotConfig(){
  try{
    const f=await gh(`/repos/${REPO}/contents/${BOT_CFG_PATH}?ref=main`);
    botCfgSha=f.sha;
    botCfg=JSON.parse(fromB64(f.content));
    updateBotUI();
  }catch(e){
    $('#bot-status-pill').textContent='Unknown';
    $('#bot-msg').textContent='Default config active';
  }
}
function updateBotUI(){
  const p=botCfg.paused===true;
  $('#bot-status-pill').textContent=p?'⏸ PAUSED':'▶ ACTIVE';
  $('#bot-status-pill').style.color=p?'#ffd15c':'#c6ff3d';
  $('#bot-toggle').textContent=p?'▶ Resume Robot':'⏸ Pause Robot';
  if(botCfg.interval_hours)$('#bot-interval').value=String(botCfg.interval_hours);
}
async function saveBotConfig(){
  $('#bot-msg').textContent='Saving schedule…';
  try{
    const content=enc(JSON.stringify(botCfg,null,2));
    const r=await gh(`/repos/${REPO}/contents/${BOT_CFG_PATH}`,{
      method:'PUT',
      body:JSON.stringify({message:`Control room: set robot schedule (paused=${botCfg.paused}, interval=${botCfg.interval_hours}h)`,content,branch:'main',...(botCfgSha?{sha:botCfgSha}:{})})
    });
    if(r&&r.content)botCfgSha=r.content.sha;
    $('#bot-msg').textContent='Robot schedule saved!';
    setTimeout(()=>{$('#bot-msg').textContent=''},3000);
  }catch(e){$('#bot-msg').textContent='Failed to save schedule: '+e.message}
}

// Change one website
function change(s,fields,lock=true){Object.assign(s,fields);if(lock&&!('locked'in fields)){s.locked=true;s.confidence=1}
  edits[s.url]={...(edits[s.url]||{}),...fields,...(lock&&!('locked'in fields)?{locked:true,confidence:1}:{})};
  const a=added.find(x=>x.url===s.url);if(a)Object.assign(a,s)}

function remove(s){
  db.sites=db.sites.filter(x=>x!==s);
  if(added.includes(s))added=added.filter(x=>x!==s);
  else deleted.add(s.url);
  delete edits[s.url];selected.delete(s.url);
}

function block(s){
  const h=hostKey(s.url);
  if(h)pendingBlocks.add(h);
  remove(s);
}

const rev=s=>s.review||'unreviewed';
function rows(){
  const q=$('#filter').value.toLowerCase(),fc=$('#fcat').value,fs=$('#fstatus').value,fr=$('#freview').value,fb=$('#fbrick')?.value||'',unsure=$('#funsure').checked,sort=$('#fsort').value;
  const r=db.sites.filter(x=>(!q||(x.title+' '+x.url+' '+x.description).toLowerCase().includes(q))&&(!fc||x.category===fc)&&(!fs||x.status===fs)&&(!fr||rev(x)===fr||(fr==='locked'&&x.locked))&&(!fb||(fb==='brick'?x.brick===true:!x.brick))&&(!unsure||(x.confidence??1)<.6));
  return r.sort(sort==='unsure'?(a,b)=>(a.confidence??1)-(b.confidence??1):sort==='old'?(a,b)=>(a.added||'').localeCompare(b.added||''):(a,b)=>(b.added||'').localeCompare(a.added||''))
}

function kpis(){
  const s=db.sites,alive=s.filter(x=>x.status!=='dead');const n=f=>alive.filter(f).length;
  $('#kpis').innerHTML=[
    ['Live',n(x=>rev(x)!=='flagged')],
    ['🧱 Brick (Immune)',s.filter(x=>x.brick===true).length],
    ['Unreviewed',n(x=>rev(x)==='unreviewed')],
    ['Verified safe',n(x=>rev(x)==='verified')],
    ['Flagged',n(x=>rev(x)==='flagged')],
    ['Hand-checked 🔒',s.filter(x=>x.locked).length],
    ['Pending Blocks',pendingBlocks.size],
    ['Retired',s.length-alive.length]
  ].map(([k,v])=>`<div><b>${v}</b>${k}</div>`).join('')
}

function card(x){
  const shot=x.screenshot_file?'screenshots/'+x.screenshot_file:'',r=rev(x);
  return `<article class="mod ${r} ${x.brick?'brick':''} ${x.status==='dead'?'dead':''} ${selected.has(x.url)?'sel':''}" data-u="${esc(x.url)}">
  <label class="pick"><input type="checkbox" data-pick ${selected.has(x.url)?'checked':''} aria-label="Select ${esc(x.title)}"></label>
  ${x.brick?'<span class="brick-badge">🧱 BRICK</span>':''}
  <a class="shot" href="${esc(x.url)}" target="_blank" rel="noopener noreferrer">${shot?`<img src="${esc(shot)}" alt="" loading="lazy" onerror="this.remove()">`:''}<span>${esc(x.url.replace(/^https?:\/\//,''))} ↗</span></a>
  <div class="fields"><input data-f="title" value="${esc(x.title)}" aria-label="Name"><textarea data-f="description" rows="3" aria-label="Description" placeholder="No description yet">${esc(x.description)}</textarea>
  <div class="line"><select data-f="category" aria-label="Category">${CATS.map(c=>`<option ${c===x.category?'selected':''}>${c}</option>`).join('')}</select><span class="pill">sure ${Math.round((x.confidence??1)*100)}%</span></div>
  <div class="line flags">
    ${Object.entries(REVIEW).map(([k,v])=>`<button data-rev="${k}" class="${r===k?'on':''}">${k==='verified'?'✓ ':k==='flagged'?'⚑ ':''}${v}</button>`).join('')}
    <button data-a="lock" title="Hand-checked websites are never changed by the robot">${x.locked?'🔒 Locked':'🔓 Unlocked'}</button>
    <button data-a="brick" class="btn-brick ${x.brick?'on':''}" title="Immune to deletion">${x.brick?'🧱 Brick':'Make Brick'}</button>
  </div>
  <div class="pill">${esc(x.status)} · ${esc(x.source||'')} · added ${esc(x.added||'?')} · checked ${esc(x.checked||'?')}${x.first_seen?' · since '+esc(x.first_seen):''}${x.embed===false?' · opens in new tab':''}${x.flag_reason?' · ⚑ '+esc(x.flag_reason):''}${x.robot_note?' · robot: '+esc(x.robot_note):''}</div>
  <div class="line">
    <button data-a="${x.status==='dead'?'revive':'kill'}">${x.status==='dead'?'↺ Revive':'Retire'}</button>
    <button data-a="del" class="danger" title="Delete from catalog">Delete</button>
    <button data-a="block" class="danger" title="Delete and permanently block domain from crawler">🚫 Block Domain</button>
  </div></div></article>`
}

function render(){
  kpis();const r=rows();$('#count').textContent=`${r.length} websites shown · ${selected.size} selected`;
  $('#save').textContent=`✓ Save changes (${dirty()})`;$('#save').disabled=!dirty();$('#batch').hidden=!selected.size;$('#bcount').textContent=selected.size+' selected';
  $('#rows').innerHTML=r.slice(0,shown).map(card).join('')||'<p class="muted">Nothing here. 🎉</p>';$('#more').hidden=r.length<=shown
}

const find=el=>db.sites.find(s=>s.url===el.closest('[data-u]').dataset.u);
$('#rows').addEventListener('change',e=>{
  const s=find(e.target);if(!s)return;
  if(e.target.dataset.pick!==undefined){e.target.checked?selected.add(s.url):selected.delete(s.url);render();return}
  const f=e.target.dataset.f;if(!f)return;change(s,{[f]:e.target.value.trim()});render()
});

$('#rows').addEventListener('click',e=>{
  const b=e.target.closest('button');if(!b)return;const s=find(b);if(!s)return;
  if(b.dataset.rev)change(s,{review:b.dataset.rev});
  const a=b.dataset.a;
  if(a==='lock')change(s,{locked:!s.locked},false);
  if(a==='brick')change(s,{brick:!s.brick});
  if(a==='kill')change(s,{status:'dead'});
  if(a==='revive')change(s,{status:'ok',fails:0});
  if(a==='del'){if(!confirm('Delete '+s.url+'? (The robot may find it again later — use Block to keep it out forever.)'))return;remove(s)}
  if(a==='block'){if(!confirm(`Permanently block and delete ${s.url}? It will NEVER be crawled or added again.`))return;block(s)}
  render()
});

$('#batch').addEventListener('click',e=>{
  const a=e.target.closest('[data-b]')?.dataset.b;if(!a)return;
  const list=db.sites.filter(s=>selected.has(s.url));
  if(a==='del'&&!confirm(`Delete ${list.length} websites?`))return;
  if(a==='block'&&!confirm(`Permanently block and delete ${list.length} domains? They will NEVER enter the catalog again.`))return;
  for(const s of list){
    if(a==='verified'||a==='flagged'||a==='unreviewed')change(s,{review:a});
    if(a==='lock')change(s,{locked:true},false);
    if(a==='unlock')change(s,{locked:false},false);
    if(a==='brick')change(s,{brick:true});
    if(a==='unbrick')change(s,{brick:false});
    if(a==='del')remove(s);
    if(a==='block')block(s);
  }
  if(a==='none'||a==='del'||a==='block')selected.clear();
  render()
});

$('#pickall').onclick=()=>{rows().slice(0,shown).forEach(s=>selected.add(s.url));render()};
$('#more').onclick=()=>{shown+=60;render()};
$('#add').onsubmit=e=>{
  e.preventDefault();let u;try{u=new URL($('#add-url').value)}catch{return msg('That address is not valid.')}
  const h=hostKey(u.href);if(db.sites.some(x=>hostKey(x.url)===h))return msg('That website is already in the list.');
  const t=new Date().toISOString().slice(0,10);
  const s={url:'https://'+h,title:$('#add-title').value.trim()||h,description:'',category:$('#add-cat').value,lang:'?',source:'admin',status:'ok',review:'verified',added:t,checked:t,fails:0,locked:true,confidence:1,brick:false};
  db.sites.unshift(s);added.push(s);$('#add').reset();render()
};

// Wipe with Brick Immunity
$('#wipe').onclick=()=>{
  const immune=db.sites.filter(s=>s.brick===true);
  const toDelete=db.sites.filter(s=>!s.brick);
  if(!confirm(`Delete all ${toDelete.length} non-brick websites? ${immune.length} 🧱 BRICK websites will be PROTECTED and preserved!`))return;
  db.sites=[...immune];db.beta_start=new Date().toISOString().slice(0,10);
  wiped=true;edits={};deleted=new Set();added=[];selected.clear();
  render();msg(`Cleaned ${toDelete.length} websites. ${immune.length} Brick websites preserved. Press 'Save changes' to commit to GitHub.`)
};

$('#run').onclick=async()=>{try{await gh(`/repos/${REPO}/actions/workflows/discover.yml/dispatches`,{method:'POST',body:JSON.stringify({ref:'main'})});msg('Robot started. New websites appear in about 10 minutes.');setTimeout(runs,4000)}catch(e){msg('Could not start the robot: '+e.message)}};
$('#save').onclick=save;$('#logout').onclick=()=>{token='';pass='';location.href='./'};

// Bot Controls events
$('#bot-toggle').onclick=()=>{botCfg.paused=!botCfg.paused;updateBotUI()};
$('#bot-interval').onchange=()=>{botCfg.interval_hours=parseInt($('#bot-interval').value,10)||1};
$('#bot-save').onclick=saveBotConfig;

for(const id of ['filter','fcat','fstatus','freview','fbrick','funsure','fsort']){const el=$('#'+id);if(el)el.oninput=()=>{shown=60;render()}}
$('#fcat').innerHTML+=CATS.map(c=>`<option>${c}</option>`).join('');$('#add-cat').innerHTML+=CATS.map(c=>`<option>${c}</option>`).join('');

const hex=b=>[...new Uint8Array(b)].map(x=>x.toString(16).padStart(2,'0')).join(''),unhex=h=>Uint8Array.from(h.match(/../g),x=>parseInt(x,16));
const sha256=async t=>hex(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(t)));
async function keyFrom(pass,salt){const base=await crypto.subtle.importKey('raw',new TextEncoder().encode(pass),'PBKDF2',false,['deriveKey']);return crypto.subtle.deriveKey({name:'PBKDF2',salt,iterations:600000,hash:'SHA-256'},base,{name:'AES-GCM',length:256},false,['encrypt','decrypt'])}
let pass='';
$('#login-form').onsubmit=async e=>{e.preventDefault();const p=$('#pass').value;$('#login-msg').textContent='Checking…';
  if(await sha256(p)!==PASS_HASH){$('#login-msg').textContent='Wrong password.';return}pass=p;
  try{const r=await fetch(VAULT+'?t='+Date.now());if(!r.ok)throw 0;const v=await r.json();
    token=new TextDecoder().decode(await crypto.subtle.decrypt({name:'AES-GCM',iv:unhex(v.iv)},await keyFrom(p,unhex(v.salt)),unhex(v.data)));await unlock()}
  catch{$('#login-msg').textContent='Password OK. No GitHub key is saved yet (or it stopped working) — do the first-time setup below.';$('#setup').hidden=false;$('#setup').open=true}};
$('#setup-form').onsubmit=async e=>{e.preventDefault();if(!pass)return;token=$('#token').value.trim();$('#login-msg').textContent='Saving…';
  try{const salt=crypto.getRandomValues(new Uint8Array(16)),iv=crypto.getRandomValues(new Uint8Array(12));
    const data=await crypto.subtle.encrypt({name:'AES-GCM',iv},await keyFrom(pass,salt),new TextEncoder().encode(token));
    const body=JSON.stringify({salt:hex(salt),iv:hex(iv),data:hex(data)});const path='docs/'+VAULT;
    const old=await gh(`/repos/${REPO}/contents/${path}?ref=main`).catch(()=>null);
    await gh(`/repos/${REPO}/contents/${path}`,{method:'PUT',body:JSON.stringify({message:'Control room: locked key',content:enc(body),branch:'main',...(old?{sha:old.sha}:{})})});
    $('#token').value='';await unlock();msg('Key locked and saved. Next time only the password is needed (on any device, after about a minute).')}
  catch(err){token='';$('#login-msg').textContent='That key did not work: '+err.message}};
window.onbeforeunload=()=>dirty()?true:undefined;

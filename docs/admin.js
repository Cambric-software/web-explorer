const REPO='Cambric-software/web-explorer',PATH='docs/data/sites.json',$=s=>document.querySelector(s);
const CATS=['Art','Business','Communities','Developer','Education','Games','Personal','Retro','Science','Technology','Tools','Random'];
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const PASS_HASH='dccf9ce19cd40e7d364d73482805b53667d1e494d2078c3952bda34a5a84e7c4',VAULT='data/admin-key.json';
let token='',db=null,sha='',dirty=0;
const gh=async(path,opt={})=>{const r=await fetch('https://api.github.com'+path,{...opt,headers:{Authorization:'Bearer '+token,Accept:'application/vnd.github+json',...(opt.headers||{})}});if(!r.ok&&r.status!==204)throw Error(r.status+' '+(await r.text()).slice(0,120));return r.status===204?null:r.json()};
const msg=t=>$('#msg').textContent=t;
const fromB64=s=>new TextDecoder().decode(Uint8Array.from(atob(s.replace(/\n/g,'')),c=>c.charCodeAt(0)));
function enc(str){const b=new TextEncoder().encode(str);let out='';for(let i=0;i<b.length;i+=0x8000)out+=String.fromCharCode(...b.subarray(i,i+0x8000));return btoa(out)}
async function unlock(){
  const repo=await gh('/repos/'+REPO);if(!repo.permissions?.push)throw Error('This account cannot edit the project.');
  const me=await gh('/user').catch(()=>({login:'owner'}));$('#who').textContent='Signed in as '+me.login;
  $('#login').hidden=true;$('#panel').hidden=false;await load();runs()}
async function load(){const f=await gh(`/repos/${REPO}/contents/${PATH}?ref=main`);sha=f.sha;
  const raw=f.content?fromB64(f.content):await (await fetch(f.download_url)).text();db=JSON.parse(raw);dirty=0;render()}
async function save(){msg('Saving…');try{const latest=await gh(`/repos/${REPO}/contents/${PATH}?ref=main`);sha=latest.sha;
  await gh(`/repos/${REPO}/contents/${PATH}`,{method:'PUT',body:JSON.stringify({message:'Control room edit',sha,content:enc(JSON.stringify(db,null,1)),branch:'main'})});
  msg('Saved. The live site updates in about a minute.');await load()}catch(e){msg('Could not save: '+e.message)}}
async function runs(){try{const r=await gh(`/repos/${REPO}/actions/workflows/discover.yml/runs?per_page=6`);
  $('#runs').innerHTML=r.workflow_runs.map(x=>`${new Date(x.created_at).toLocaleString()} — ${esc(x.conclusion||x.status)} <a href="${esc(x.html_url)}" target="_blank" rel="noopener">details ↗</a>`).join('<br>')||'No runs yet.'}catch{$('#runs').textContent='Run history unavailable (token needs Actions: read).'}}
function mark(){dirty++;$('#save').disabled=false;$('#save').textContent=`✓ Save changes (${dirty})`}
function render(){const s=db.sites,alive=s.filter(x=>x.status!=='dead');const cats={};alive.forEach(x=>cats[x.category]=(cats[x.category]||0)+1);
  $('#kpis').innerHTML=[['Alive',alive.length],['Dead',s.length-alive.length],['Added today',s.filter(x=>x.added===new Date().toISOString().slice(0,10)).length],['Hand-checked',s.filter(x=>x.locked).length],['Uncertain category',alive.filter(x=>(x.confidence??1)<.6).length]].map(([k,v])=>`<div><b>${v}</b>${k}</div>`).join('')+Object.entries(cats).sort((a,b)=>b[1]-a[1]).map(([k,v])=>`<div><b>${v}</b>${esc(k)}</div>`).join('');
  $('#save').textContent=`✓ Save changes (${dirty})`;$('#save').disabled=!dirty;
  const q=$('#filter').value.toLowerCase(),fc=$('#fcat').value,fs=$('#fstatus').value;
  const rows=s.map((x,i)=>[x,i]).filter(([x])=>(!q||(x.title+' '+x.url).toLowerCase().includes(q))&&(!fc||x.category===fc)&&(!fs||x.status===fs));
  $('#count').textContent=rows.length+' websites shown';
  $('#rows').innerHTML=rows.slice(0,300).map(([x,i])=>`<tr data-i="${i}" class="${x.status==='dead'?'dead':''}"><td><a href="${esc(x.url)}" target="_blank" rel="noopener noreferrer">${esc(x.url.replace(/^https?:\/\//,''))}</a><div class="pill">${esc(x.status)} · ${esc(x.source||'')} · checked ${esc(x.checked||'')}${x.locked?' · 🔒 hand-checked':''}</div></td><td><input data-f="title" value="${esc(x.title)}"><textarea data-f="description" rows="2">${esc(x.description)}</textarea></td><td><select data-f="category">${CATS.map(c=>`<option ${c===x.category?'selected':''}>${c}</option>`).join('')}</select><div class="pill">sure: ${Math.round((x.confidence??1)*100)}%</div></td><td><button data-a="${x.status==='dead'?'revive':'kill'}">${x.status==='dead'?'Revive':'Hide'}</button> <button data-a="del">Delete</button></td></tr>`).join('')}
$('#rows').addEventListener('change',e=>{const f=e.target.dataset.f;if(!f)return;const x=db.sites[e.target.closest('tr').dataset.i];x[f]=e.target.value.trim();x.locked=true;x.confidence=1;mark()});
$('#rows').addEventListener('click',e=>{const a=e.target.dataset.a;if(!a)return;const i=+e.target.closest('tr').dataset.i,x=db.sites[i];
  if(a==='del'){if(!confirm('Delete '+x.url+'?'))return;db.sites.splice(i,1)}if(a==='kill'){x.status='dead';x.locked=true}if(a==='revive'){x.status='ok';x.fails=0}mark();render()});
$('#add').onsubmit=e=>{e.preventDefault();let u;try{u=new URL($('#add-url').value)}catch{return msg('That address is not valid.')}const h=u.hostname.replace(/^www\./,'');
  if(db.sites.some(x=>new URL(x.url).hostname.replace(/^www\./,'')===h))return msg('That website is already in the list.');const t=new Date().toISOString().slice(0,10);
  db.sites.unshift({url:'https://'+h,title:$('#add-title').value.trim()||h,description:'',category:$('#add-cat').value,lang:'?',source:'admin',status:'ok',added:t,checked:t,fails:0,locked:true,confidence:1});$('#add').reset();mark();render()};
$('#wipe').onclick=()=>{if(!confirm('Delete EVERY website? The robot will start again from zero.'))return;db.sites=[];db.beta_start=new Date().toISOString().slice(0,10);mark();render();msg('Press Save to make it real.')};
$('#run').onclick=async()=>{try{await gh(`/repos/${REPO}/actions/workflows/discover.yml/dispatches`,{method:'POST',body:JSON.stringify({ref:'main'})});msg('Robot started. New websites appear in about 5 minutes.');setTimeout(runs,4000)}catch(e){msg('Could not start the robot: '+e.message)}};
$('#save').onclick=save;$('#logout').onclick=()=>{token='';pass='';location.href='./'};
for(const id of ['filter','fcat','fstatus'])$('#'+id).oninput=render;
$('#fcat').innerHTML+=CATS.map(c=>`<option>${c}</option>`).join('');$('#add-cat').innerHTML=CATS.map(c=>`<option>${c}</option>`).join('');
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
window.onbeforeunload=()=>dirty?true:undefined;

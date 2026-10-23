const REPO='Cambric-software/web-explorer',PATH='docs/data/sites.json',$=s=>document.querySelector(s);
const CATS=['Art','Business','Communities','Developer','Education','Games','Personal','Retro','Science','Technology','Tools','Random'];
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let token=sessionStorage.getItem('we_admin')||'',db=null,sha='',dirty=0;
const gh=async(path,opt={})=>{const r=await fetch('https://api.github.com'+path,{...opt,headers:{Authorization:'Bearer '+token,Accept:'application/vnd.github+json',...(opt.headers||{})}});if(!r.ok&&r.status!==204)throw Error(r.status+' '+(await r.text()).slice(0,120));return r.status===204?null:r.json()};
const msg=t=>$('#msg').textContent=t;
const fromB64=s=>new TextDecoder().decode(Uint8Array.from(atob(s.replace(/\n/g,'')),c=>c.charCodeAt(0)));
function enc(str){const b=new TextEncoder().encode(str);let out='';for(let i=0;i<b.length;i+=0x8000)out+=String.fromCharCode(...b.subarray(i,i+0x8000));return btoa(out)}
async function unlock(){
  const repo=await gh('/repos/'+REPO);if(!repo.permissions?.push)throw Error('This account cannot edit the project.');
  const me=await gh('/user').catch(()=>({login:'owner'}));$('#who').textContent='Signed in as '+me.login;
  sessionStorage.setItem('we_admin',token);$('#login').hidden=true;$('#panel').hidden=false;await load();runs()}
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
$('#save').onclick=save;$('#logout').onclick=()=>{sessionStorage.removeItem('we_admin');location.href='./'};
for(const id of ['filter','fcat','fstatus'])$('#'+id).oninput=render;
$('#fcat').innerHTML+=CATS.map(c=>`<option>${c}</option>`).join('');$('#add-cat').innerHTML=CATS.map(c=>`<option>${c}</option>`).join('');
$('#login-form').onsubmit=async e=>{e.preventDefault();token=$('#token').value.trim();$('#login-msg').textContent='Checking…';try{await unlock()}catch(err){token='';$('#login-msg').textContent='Not allowed: '+err.message}};
window.onbeforeunload=()=>dirty?true:undefined;
if(token)unlock().catch(()=>{sessionStorage.removeItem('we_admin');token=''});

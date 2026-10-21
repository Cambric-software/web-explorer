(function(root){
 const ranks=['Explorer','Scout','Navigator','Pathfinder','Adventurer','Master Explorer','Internet Cartographer','Legendary Explorer'];
 const thresholds=[0,10,25,50,100,250,500,1000];
 function rank(n){let i=thresholds.findLastIndex(t=>n>=t);i=Math.max(0,i);return {name:ranks[i],next:thresholds[i+1]??null,start:thresholds[i],progress:i===7?100:Math.min(100,(n-thresholds[i])/(thresholds[i+1]-thresholds[i])*100)}}
 function matches(s,f={}){const y=Number(s.first_seen);return (!f.category||s.category===f.category)&&(!f.lang||s.lang===f.lang)&&(!f.q||(s.title+' '+s.description+' '+s.url).toLowerCase().includes(f.q.toLowerCase()))&&(!f.decade||(y>0&&(f.decade==='google'?y<1998:Math.floor(y/10)*10===Number(f.decade))))&&!(f.excluded||[]).includes(s.category)&&(!f.hideDisliked||(f.votes?.[s.url]||0)>=0)}
 function daily(sites,date){if(!sites.length)return null;let n=0;for(const c of date)n=(n*31+c.charCodeAt(0))>>>0;const sorted=[...sites].sort((a,b)=>a.url.localeCompare(b.url));return sorted[n%sorted.length]}
 const api={rank,matches,daily,safeUrl:u=>{try{const p=new URL(u);return ['http:','https:'].includes(p.protocol)?p.href:null}catch{return null}}};root.ExplorerCore=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);

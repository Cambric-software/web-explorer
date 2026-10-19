import { useEffect, useState } from "react";
import { api, post, Website } from "../api";
import { useMe } from "../App";

const VOTES = [["like","👍 Like"],["gem","❤️ Hidden Gem"],["dislike","👎 Dislike"],["favorite","⭐ Favorite"]] as const;

export default function SiteCard({ site, compact }: { site: Website; compact?: boolean }) {
  const { me } = useMe();
  const [active, setActive] = useState<string[]>([]);
  const [score, setScore] = useState(site.hidden_gem_score);
  const [cols, setCols] = useState<{ id: number; name: string }[]>([]);
  useEffect(() => { setScore(site.hidden_gem_score); if (me && !compact) { api(`/api/websites/${site.id}/my-votes`).then(setActive); api("/api/collections").then(setCols); } }, [site.id, me]);
  const vote = async (kind: string) => {
    if (!me) return alert("Log in to vote");
    const r = await post(`/api/websites/${site.id}/vote`, { kind });
    setScore(r.hidden_gem_score);
    setActive(a => { let n = a.filter(k => k !== kind); if (r.active) { n.push(kind); if (kind === "like") n = n.filter(k => k !== "dislike"); if (kind === "dislike") n = n.filter(k => k !== "like"); } return n; });
  };
  return (
    <div className="card">
      <div className="flex items-center gap-3 font-mono text-xs text-dim">
        <span className="rounded border border-signal px-2 py-0.5 text-signal">{site.category}</span>
        {site.language && <span>{site.language}</span>}
        <span className="ml-auto text-gem">gem score {score}</span>
      </div>
      <h2 className={`mt-3 font-bold ${compact ? "text-lg" : "text-3xl"}`}>{site.title}</h2>
      <p className="mt-2 text-dim">{site.description}</p>
      <p className="mt-3 truncate font-mono text-sm text-gold">{site.url}</p>
      <div className="mt-5 flex flex-wrap gap-2">
        <a href={site.url} target="_blank" rel="noopener noreferrer" className="btn btn-on">Open Website ↗</a>
        {!compact && VOTES.map(([k, l]) => <button key={k} onClick={() => vote(k)} className={`btn ${active.includes(k) ? "btn-on" : ""}`}>{l}</button>)}
        {!compact && me && cols.length > 0 && (
          <select className="btn" defaultValue="" onChange={e => { post(`/api/collections/${e.target.value}/items/${site.id}`); e.target.value = ""; }}>
            <option value="" disabled>+ collection</option>
            {cols.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>)}
      </div>
    </div>
  );
}

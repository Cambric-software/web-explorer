import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, token, Website } from "../api";
import { useMe } from "../App";
import SiteCard from "./SiteCard";

export default function Profile() {
  const { me, refresh } = useMe();
  const nav = useNavigate();
  const [tab, setTab] = useState<"favorites" | "history">("favorites");
  const [list, setList] = useState<Website[]>([]);
  useEffect(() => { if (me) api(`/api/me/${tab}`).then(setList); }, [tab, me]);
  if (!me) return <p className="text-dim">Log in to see your profile.</p>;
  const s = me.stats;
  return (
    <div>
      <div className="card">
        <p className="font-mono text-xs text-dim">RANK</p>
        <h1 className="text-4xl font-bold text-signal">{s.rank}</h1>
        <p className="mt-1">{me.username}</p>
        <div className="mt-5 grid grid-cols-2 gap-3 font-mono md:grid-cols-4">
          <div><div className="text-2xl">{s.sites_discovered}</div><div className="text-xs text-dim">sites discovered</div></div>
          <div><div className="text-2xl">{s.sites_visited}</div><div className="text-xs text-dim">sites visited</div></div>
          <div><div className="text-2xl">{s.hidden_gems_found}</div><div className="text-xs text-dim">hidden gems</div></div>
          <div><div className="text-sm">{s.favorite_categories.join(", ") || "—"}</div><div className="text-xs text-dim">favorite categories</div></div>
        </div>
        <div className="mt-5 flex flex-wrap gap-2">{s.badges.map((b: string) => <span key={b} className="rounded-full border border-gold px-3 py-1 font-mono text-xs text-gold">🏅 {b}</span>)}
          {!s.badges.length && <span className="font-mono text-xs text-dim">No badges yet — keep exploring.</span>}</div>
        <button className="btn mt-5" onClick={() => { token.set(null); refresh(); nav("/"); }}>log out</button>
      </div>
      <div className="mt-6 flex gap-2">
        <button className={`btn ${tab === "favorites" ? "btn-on" : ""}`} onClick={() => setTab("favorites")}>Favorites</button>
        <button className={`btn ${tab === "history" ? "btn-on" : ""}`} onClick={() => setTab("history")}>History</button>
      </div>
      <div className="mt-4 grid gap-4 md:grid-cols-2">{list.map((w, i) => <SiteCard key={w.id + "-" + i} site={w} compact />)}</div>
    </div>
  );
}

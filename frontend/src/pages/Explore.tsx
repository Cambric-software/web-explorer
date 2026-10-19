import { useEffect, useState } from "react";
import { api, post, Website } from "../api";
import SiteCard from "./SiteCard";

export default function Explore() {
  const [site, setSite] = useState<Website | null>(null);
  const [info, setInfo] = useState("");
  const [loading, setLoading] = useState(false);
  const [cats, setCats] = useState<string[]>([]);
  const [cat, setCat] = useState("Random");
  const [stats, setStats] = useState<any>(null);
  const [sub, setSub] = useState("");
  useEffect(() => { api("/api/categories").then(setCats); api("/api/stats").then(setStats); }, []);
  const go = async () => {
    setLoading(true); setInfo("");
    try {
      const r = await api(`/api/explore?category=${cat}`);
      setSite(r.website);
      setInfo(`${r.mode} mode · ${r.newly_discovered} new sites verified`);
      api("/api/stats").then(setStats);
    } catch (e: any) { setInfo(e.message); } finally { setLoading(false); }
  };
  return (
    <div>
      <section className="py-16 text-center">
        <h1 className="text-5xl font-bold md:text-7xl">Discover the<br /><span className="text-signal">Internet Again.</span></h1>
        <p className="mx-auto mt-4 max-w-md text-dim">Real, verified websites. Hidden gems, indie projects and forgotten corners of the web.</p>
        <div className="mt-8 flex flex-wrap justify-center gap-2">
          {cats.map(c => <button key={c} onClick={() => setCat(c)} className={`btn !px-3 !py-1 text-xs ${cat === c ? "btn-on" : ""}`}>{c}</button>)}
        </div>
        <button onClick={go} disabled={loading} className="explore-btn mt-10 rounded-full bg-signal px-14 py-5 font-mono text-xl font-bold text-bg disabled:opacity-60">
          {loading ? "SCANNING…" : "EXPLORE"}
        </button>
        {info && <p className="mt-4 font-mono text-xs text-dim">{info}</p>}
      </section>
      {site && <SiteCard site={site} />}
      {stats && (
        <div className="mt-10 grid grid-cols-3 gap-3 text-center font-mono">
          <div className="card"><div className="text-2xl text-signal">{stats.total_websites}</div><div className="text-xs text-dim">verified sites</div></div>
          <div className="card"><div className="text-2xl text-gold">{stats.discovered_today}</div><div className="text-xs text-dim">found today</div></div>
          <div className="card"><div className="text-2xl text-gem">{stats.total_visits}</div><div className="text-xs text-dim">explorations</div></div>
        </div>)}
      <form className="mt-10 flex gap-2" onSubmit={async e => { e.preventDefault(); const r = await post("/api/submit", { url: sub }); alert(r.status); setSub(""); }}>
        <input className="input" placeholder="Submit a website you love…" value={sub} onChange={e => setSub(e.target.value)} required />
        <button className="btn">Submit</button>
      </form>
    </div>
  );
}

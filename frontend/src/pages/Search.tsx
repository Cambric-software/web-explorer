import { useEffect, useState } from "react";
import { api, Website } from "../api";
import SiteCard from "./SiteCard";

export default function Search() {
  const [q, setQ] = useState("");
  const [sort, setSort] = useState("gem");
  const [res, setRes] = useState<Website[]>([]);
  const run = () => api(`/api/search?q=${encodeURIComponent(q)}&sort=${sort}`).then(setRes);
  useEffect(() => { run(); }, [sort]);
  return (
    <div>
      <form className="flex gap-2" onSubmit={e => { e.preventDefault(); run(); }}>
        <input className="input" placeholder='Try "retro websites", "japanese", "ai tools"' value={q} onChange={e => setQ(e.target.value)} />
        <select className="btn" value={sort} onChange={e => setSort(e.target.value)}>
          <option value="gem">hidden gems</option><option value="new">newest</option><option value="popular">popular</option>
        </select>
        <button className="btn btn-on">Search</button>
      </form>
      <div className="mt-6 grid gap-4 md:grid-cols-2">{res.map(s => <SiteCard key={s.id} site={s} compact />)}</div>
      {!res.length && <p className="mt-10 text-center text-dim">No results yet.</p>}
    </div>
  );
}

import { useEffect, useState } from "react";
import { api, post, Website } from "../api";

type Col = { id: number; name: string; websites: Website[] };
export default function Collections() {
  const [cols, setCols] = useState<Col[]>([]);
  const [name, setName] = useState("");
  const load = () => api("/api/collections").then(setCols);
  useEffect(() => { load(); }, []);
  return (
    <div>
      <form className="flex gap-2" onSubmit={async e => { e.preventDefault(); await post("/api/collections", { name }); setName(""); load(); }}>
        <input className="input" placeholder="New collection, e.g. Cool Retro Sites" value={name} onChange={e => setName(e.target.value)} required />
        <button className="btn btn-on">Create</button>
      </form>
      <div className="mt-6 space-y-4">
        {cols.map(c => (
          <div key={c.id} className="card">
            <div className="flex items-center"><h3 className="text-xl font-bold">{c.name}</h3>
              <button className="btn ml-auto !py-1 text-xs" onClick={async () => { await api(`/api/collections/${c.id}`, { method: "DELETE" }); load(); }}>delete</button></div>
            <ul className="mt-3 space-y-1 font-mono text-sm">
              {c.websites.map(w => <li key={w.id} className="flex gap-2"><a className="text-gold hover:underline" href={w.url} target="_blank" rel="noreferrer">{w.title}</a>
                <button className="text-dim hover:text-gem" onClick={async () => { await api(`/api/collections/${c.id}/items/${w.id}`, { method: "DELETE" }); load(); }}>×</button></li>)}
              {!c.websites.length && <li className="text-dim">Empty — add sites from the Explore screen.</li>}
            </ul>
          </div>))}
      </div>
    </div>
  );
}

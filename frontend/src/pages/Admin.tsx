import { useEffect, useState } from "react";
import { api, post, Website } from "../api";
import { useMe } from "../App";

export default function Admin() {
  const { me } = useMe();
  const [s, setS] = useState<any>(null);
  const [status, setStatus] = useState("dead");
  const [sites, setSites] = useState<Website[]>([]);
  const load = () => { api("/api/admin/stats").then(setS); api(`/api/admin/websites?status=${status}`).then(setSites); };
  useEffect(() => { if (me?.is_admin) load(); }, [me, status]);
  if (!me?.is_admin) return <p className="text-dim">Admins only.</p>;
  if (!s) return null;
  const tiles = [["Total Websites", s.total_websites],["Alive", s.alive],["New (7d)", s.new_websites_7d],["Dead Websites", s.dead_websites],
    ["Awaiting Re-verify", s.pending_reverification],["Verified (7d)", s.verified_last_7d],["Submissions", s.pending_submissions],
    ["Users", s.users],["New Users (7d)", s.new_users_7d],["Visits (7d)", s.visits_7d],["Votes", s.votes_total],["Phase", s.beta ? "BETA" : "LIVE"]];
  return (
    <div>
      <div className="flex gap-2"><h1 className="mr-auto text-3xl font-bold">Admin Dashboard</h1>
        <button className="btn" onClick={() => post("/api/admin/discover").then(() => alert("Discovery queued"))}>Run discovery</button>
        <button className="btn" onClick={() => post("/api/admin/reverify").then(() => alert("Re-verification queued"))}>Re-verify</button></div>
      <div className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-4">
        {tiles.map(([l, v]) => <div key={l} className="card"><div className="font-mono text-2xl text-signal">{v}</div><div className="text-xs text-dim">{l}</div></div>)}
      </div>
      <div className="mt-6 grid gap-3 md:grid-cols-2">
        {[["By category", s.by_category], ["By source", s.by_source]].map(([t, obj]: any) => (
          <div key={t} className="card"><h3 className="font-bold">{t}</h3>
            {Object.entries(obj).map(([k, v]: any) => <div key={k} className="mt-1 flex font-mono text-sm"><span className="text-dim">{k}</span><span className="ml-auto">{v}</span></div>)}</div>))}
      </div>
      <div className="mt-6 flex gap-2">{["dead","alive","blocked"].map(x => <button key={x} className={`btn ${status === x ? "btn-on" : ""}`} onClick={() => setStatus(x)}>{x}</button>)}</div>
      <table className="mt-3 w-full font-mono text-xs">
        <tbody>{sites.map(w => <tr key={w.id} className="border-b border-line">
          <td className="py-2 text-gold">{w.url}</td><td>{w.category}</td><td>{new Date(w.last_verified).toLocaleDateString()}</td>
          <td className="text-right">{["alive","dead","blocked"].filter(x => x !== w.status).map(x =>
            <button key={x} className="ml-2 text-dim hover:text-signal" onClick={() => post(`/api/admin/websites/${w.id}/status?status=${x}`).then(load)}>→{x}</button>)}</td></tr>)}</tbody>
      </table>
    </div>
  );
}

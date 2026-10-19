import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { post, token } from "../api";
import { useMe } from "../App";

export default function Login() {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [f, setF] = useState({ email: "", username: "", password: "" });
  const [err, setErr] = useState("");
  const { refresh } = useMe(); const nav = useNavigate();
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setErr("");
    try { const r = await post(`/api/auth/${mode}`, f); token.set(r.access_token); refresh(); nav("/"); } catch (x: any) { setErr(x.message); }
  };
  return (
    <form onSubmit={submit} className="card mx-auto mt-10 max-w-sm space-y-3">
      <h1 className="text-2xl font-bold">{mode === "login" ? "Welcome back, explorer" : "Become an explorer"}</h1>
      <input className="input" type="email" placeholder="email" value={f.email} onChange={e => setF({ ...f, email: e.target.value })} required />
      {mode === "register" && <input className="input" placeholder="username" value={f.username} onChange={e => setF({ ...f, username: e.target.value })} required />}
      <input className="input" type="password" placeholder="password (8+ chars)" value={f.password} onChange={e => setF({ ...f, password: e.target.value })} required />
      {err && <p className="text-sm text-gem">{err}</p>}
      <button className="btn btn-on w-full">{mode === "login" ? "Log in" : "Create account"}</button>
      <button type="button" className="w-full font-mono text-xs text-dim" onClick={() => setMode(mode === "login" ? "register" : "login")}>
        {mode === "login" ? "No account? Register" : "Have an account? Log in"}</button>
    </form>
  );
}

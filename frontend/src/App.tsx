import { createContext, useContext, useEffect, useState } from "react";
import { Link, NavLink, Route, Routes } from "react-router-dom";
import { api, token } from "./api";
import Explore from "./pages/Explore";
import Search from "./pages/Search";
import Collections from "./pages/Collections";
import Profile from "./pages/Profile";
import Admin from "./pages/Admin";
import Login from "./pages/Login";

type Me = { username: string; is_admin: boolean; stats: any } | null;
const Ctx = createContext<{ me: Me; refresh: () => void }>({ me: null, refresh: () => {} });
export const useMe = () => useContext(Ctx);

export default function App() {
  const [me, setMe] = useState<Me>(null);
  const refresh = () => token.get() ? api("/api/me").then(setMe).catch(() => { token.set(null); setMe(null); }) : setMe(null);
  useEffect(() => { refresh(); }, []);
  const nav = ({ isActive }: { isActive: boolean }) => `font-mono text-sm ${isActive ? "text-signal" : "text-dim hover:text-ink"}`;
  return (
    <Ctx.Provider value={{ me, refresh }}>
      <header className="mx-auto flex max-w-5xl items-center justify-between px-6 py-5">
        <Link to="/" className="flex items-center gap-2 text-lg font-bold"><span className="text-signal">◉</span> Website Explorer</Link>
        <nav className="flex gap-5">
          <NavLink to="/" end className={nav}>explore</NavLink>
          <NavLink to="/search" className={nav}>search</NavLink>
          {me && <NavLink to="/collections" className={nav}>collections</NavLink>}
          {me ? <NavLink to="/profile" className={nav}>{me.username}</NavLink> : <NavLink to="/login" className={nav}>login</NavLink>}
          {me?.is_admin && <NavLink to="/admin" className={nav}>admin</NavLink>}
        </nav>
      </header>
      <main className="mx-auto max-w-5xl px-6 pb-20">
        <Routes>
          <Route path="/" element={<Explore />} />
          <Route path="/search" element={<Search />} />
          <Route path="/collections" element={<Collections />} />
          <Route path="/profile" element={<Profile />} />
          <Route path="/admin" element={<Admin />} />
          <Route path="/login" element={<Login />} />
        </Routes>
      </main>
      <footer className="pb-8 text-center font-mono text-xs text-dim">Cambric Software & Hardware Studios</footer>
    </Ctx.Provider>
  );
}

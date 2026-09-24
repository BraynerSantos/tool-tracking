import { useEffect, useState } from 'react';
import { Outlet, Link, useNavigate } from 'react-router-dom';
import { useAuth } from './auth.jsx';
import { api } from './api.js';

export default function Layout() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [companyName, setCompanyName] = useState('');
  useEffect(() => {
    api('/config').then(c => setCompanyName(c.companyName || '')).catch(() => {});
  }, []);
  useEffect(() => {
    document.title = companyName || 'Tool DB';
  }, [companyName]);
  return (
    <div className="min-h-screen bg-slate-100">
      <header className="no-print bg-slate-900 text-white px-6 py-3 flex items-center gap-6">
        <Link to="/" className="font-bold text-lg tracking-tight">
          {companyName ? `${companyName} — Tool DB` : 'Tool DB'}
        </Link>
        <nav className="flex gap-4 text-sm">
          <Link to="/" className="hover:text-sky-300">Search</Link>
          <Link to="/tools/new" className="hover:text-sky-300">Add tool</Link>
          {user?.isAdmin && <Link to="/admin" className="hover:text-sky-300">Admin</Link>}
        </nav>
        <div className="ml-auto flex items-center gap-3 text-sm">
          <span className="text-slate-300">{user?.name} ({user?.badgeId})</span>
          <button onClick={async () => { await logout(); nav('/login'); }}
            className="bg-slate-700 hover:bg-slate-600 rounded px-3 py-1">Log out</button>
        </div>
      </header>
      <main className="max-w-6xl mx-auto p-6"><Outlet /></main>
    </div>
  );
}

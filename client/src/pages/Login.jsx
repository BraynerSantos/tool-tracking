import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../auth.jsx';
import { api } from '../api.js';

export default function Login() {
  const { user, login } = useAuth();
  const nav = useNavigate();
  const [badgeId, setBadgeId] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [error, setError] = useState('');

  useEffect(() => { if (user) nav('/', { replace: true }); }, [user, nav]);
  useEffect(() => {
    if (badgeId.trim().length < 2) { setSuggestions([]); return; }
    let live = true;
    api(`/employee-lookup?q=${encodeURIComponent(badgeId)}`)
      .then(list => { if (live) setSuggestions(list.slice(0, 5)); })
      .catch(() => {});
    return () => { live = false; };
  }, [badgeId]);

  const submit = async e => {
    e.preventDefault();
    setError('');
    try { await login(badgeId.trim()); nav('/', { replace: true }); }
    catch (err) { setError(err.message); }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-100">
      <form onSubmit={submit} className="bg-white shadow-lg rounded-xl p-8 w-80 space-y-4">
        <h1 className="text-2xl font-bold text-slate-800">Tool DB</h1>
        <label className="block text-sm font-medium text-slate-600">Employee ID</label>
        <input autoFocus value={badgeId} onChange={e => setBadgeId(e.target.value)}
          className="w-full border border-slate-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-sky-500"
          placeholder="Scan or type your badge ID" />
        {suggestions.length > 0 && (
          <ul className="border border-slate-200 rounded-lg divide-y divide-slate-100 text-sm">
            {suggestions.map(s => (
              <li key={s.badgeId}>
                <button type="button" onClick={() => setBadgeId(s.badgeId)}
                  className="w-full text-left px-3 py-2 hover:bg-slate-50">
                  {s.name} <span className="text-slate-400">({s.badgeId})</span>
                </button>
              </li>
            ))}
          </ul>
        )}
        {error && <p className="text-red-600 text-sm">{error}</p>}
        <button className="w-full bg-sky-600 hover:bg-sky-500 text-white rounded-lg py-2 font-medium">
          Log in
        </button>
      </form>
    </div>
  );
}

import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api } from '../api.js';

export default function ToolDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const [tool, setTool] = useState(null);
  const [error, setError] = useState('');

  const load = () => api(`/tools/${id}`).then(setTool).catch(e => setError(e.message));
  useEffect(() => { load(); }, [id]);

  if (error) return <p className="text-red-600">{error}</p>;
  if (!tool) return <p className="text-slate-500">Loading…</p>;
  const attrs = Object.entries(tool.attributes).filter(([, v]) => v !== '' && v != null);
  const low = tool.reorderMin != null && tool.inventory.reduce((s, l) => s + l.quantity, 0) <= tool.reorderMin;

  return (
    <div className="space-y-4 max-w-4xl">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">{tool.name}</h1>
          <p className="text-slate-500">{tool.typeName}{tool.description ? ` — ${tool.description}` : ''}</p>
          {low && <span className="text-xs bg-amber-100 text-amber-800 rounded px-1.5 py-0.5">low stock</span>}
        </div>
        <div className="no-print flex gap-2">
          <Link to={`/tools/${tool.id}/edit`} className="bg-sky-600 hover:bg-sky-500 text-white rounded-lg px-4 py-2 text-sm">Edit</Link>
          <button onClick={async () => {
            if (!confirm(`Delete "${tool.name}"? This cannot be undone.`)) return;
            await api(`/tools/${tool.id}`, { method: 'DELETE' });
            nav('/');
          }} className="bg-red-600 hover:bg-red-500 text-white rounded-lg px-4 py-2 text-sm">Delete</button>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="font-medium text-slate-700 mb-3">Attributes</h2>
          <dl className="text-sm space-y-1">
            {attrs.length === 0 && <p className="text-slate-400">None</p>}
            {attrs.map(([k, v]) => <div key={k} className="flex justify-between gap-4 border-b border-slate-100 py-1">
              <dt className="text-slate-500">{k.replace(/_/g, ' ')}</dt><dd className="font-medium">{String(v)}</dd>
            </div>)}
          </dl>
          {tool.notes && <p className="mt-3 text-sm text-slate-600">Notes: {tool.notes}</p>}
          {tool.reorderMin != null && <p className="mt-1 text-sm text-slate-600">Reorder minimum: {tool.reorderMin}</p>}
        </div>
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="font-medium text-slate-700 mb-3">Where it is</h2>
          <table className="w-full text-sm">
            <tbody>
              {tool.inventory.length === 0 && <tr><td className="text-slate-400">No inventory recorded.</td></tr>}
              {tool.inventory.map(l => (
                <tr key={l.locationId} className="border-b border-slate-100">
                  <td className="py-1.5 text-slate-600">{l.departmentName} — {l.locationName}</td>
                  <td className="py-1.5 text-right font-semibold">{l.quantity}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="font-medium text-slate-700 mb-3">History</h2>
        <ul className="text-sm text-slate-600 space-y-1">
          {tool.history.map((h, i) => (
            <li key={i}>{h.timestamp} — {h.badgeId} — {h.action}{h.details ? ` — ${h.details}` : ''}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}

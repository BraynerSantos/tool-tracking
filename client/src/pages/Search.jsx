import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../api.js';

export default function Search() {
  const [params, setParams] = useSearchParams();
  const q = params.get('q') ?? '';
  const typeId = params.get('typeId') ?? '';
  const departmentId = params.get('departmentId') ?? '';
  const locationId = params.get('locationId') ?? '';

  const [types, setTypes] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [data, setData] = useState({ results: [], locationsByTool: {} });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api('/tool-types'), api('/departments')])
      .then(([t, d]) => { setTypes(t); setDepartments(d); })
      .catch(() => {});
  }, []);

  useEffect(() => {
    let live = true;
    setLoading(true);
    const qs = new URLSearchParams({ q, typeId, departmentId, locationId });
    api(`/tools?${qs}`).then(d => { if (live) setData(d); }).finally(() => live && setLoading(false));
    return () => { live = false; };
  }, [q, typeId, departmentId, locationId]);

  // One setParams call per event: sequential calls would each build from the
  // stale params closure and the last navigation would win.
  const set = (updates) => {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(updates)) {
      if (value) next.set(key, value); else next.delete(key);
    }
    setParams(next, { replace: true });
  };
  const exportUrl = useMemo(() => {
    const qs = new URLSearchParams({ q, typeId, departmentId, locationId });
    return `/api/export.csv?${qs}`;
  }, [q, typeId, departmentId, locationId]);

  const department = departments.find(d => String(d.id) === String(departmentId));
  const locations = department?.locations ?? [];

  return (
    <div className="space-y-4">
      <div className="flex gap-2 flex-wrap">
        <input value={q} onChange={e => set({ q: e.target.value })}
          placeholder="Search tools and attributes — e.g. 6mm, HSK, TiAlN"
          className="flex-1 min-w-64 border border-slate-300 rounded-lg px-4 py-2 text-lg focus:outline-none focus:ring-2 focus:ring-sky-500" />
        <button onClick={() => window.print()}
          className="no-print bg-slate-700 hover:bg-slate-600 text-white rounded-lg px-4 py-2">Print</button>
        <a href={exportUrl}
          className="no-print bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg px-4 py-2">Export CSV</a>
        <Link to="/tools/new"
          className="no-print bg-sky-600 hover:bg-sky-500 text-white rounded-lg px-4 py-2 font-medium">+ Add tool</Link>
      </div>
      <div className="no-print flex gap-2 flex-wrap text-sm">
        <select value={typeId} onChange={e => set({ typeId: e.target.value })}
          className="border border-slate-300 rounded-lg px-3 py-1.5 bg-white">
          <option value="">All types</option>
          {types.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>
        <select value={departmentId} onChange={e => set({ departmentId: e.target.value, locationId: '' })}
          className="border border-slate-300 rounded-lg px-3 py-1.5 bg-white">
          <option value="">All departments</option>
          {departments.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
        <select value={locationId} onChange={e => set({ locationId: e.target.value })} disabled={!departmentId}
          className="border border-slate-300 rounded-lg px-3 py-1.5 bg-white disabled:bg-slate-200">
          <option value="">All locations</option>
          {locations.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
        </select>
        <span className="self-center text-slate-500">
          {loading ? 'Searching…' : `${data.results.length} tool${data.results.length === 1 ? '' : 's'}`}
        </span>
      </div>
      <table className="w-full bg-white rounded-lg shadow text-sm">
        <thead>
          <tr className="text-left text-slate-500 border-b border-slate-200">
            <th className="p-3">Tool</th><th className="p-3">Type</th>
            <th className="p-3">Key attributes</th><th className="p-3">Locations</th>
            <th className="p-3 text-right">Total qty</th>
          </tr>
        </thead>
        <tbody>
          {data.results.map(tool => {
            const attrs = Object.entries(tool.attributes).filter(([, v]) => v !== '' && v != null);
            const low = tool.reorderMin != null && tool.totalQty <= tool.reorderMin;
            return (
              <tr key={tool.id} className="border-b border-slate-100 hover:bg-slate-50">
                <td className="p-3">
                  <Link to={`/tools/${tool.id}`} className="font-medium text-sky-700 hover:underline">{tool.name}</Link>
                  {low && <span className="ml-2 text-xs bg-amber-100 text-amber-800 rounded px-1.5 py-0.5">low stock</span>}
                  {tool.description && <div className="text-slate-500">{tool.description}</div>}
                </td>
                <td className="p-3 text-slate-600">{tool.typeName}</td>
                <td className="p-3 text-slate-600">{attrs.map(([k, v]) => String(v)).join(' · ')}</td>
                <td className="p-3 text-slate-600">
                  {(data.locationsByTool[tool.id] ?? [])
                    .map(l => `${l.departmentName} – ${l.locationName}: ${l.quantity}`).join(' · ') || '—'}
                </td>
                <td className={`p-3 text-right font-semibold ${low ? 'text-amber-700' : 'text-slate-800'}`}>{tool.totalQty}</td>
              </tr>
            );
          })}
          {!loading && data.results.length === 0 && (
            <tr><td colSpan={5} className="p-8 text-center text-slate-400">No tools match your search.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

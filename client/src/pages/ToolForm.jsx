import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api } from '../api.js';

export default function ToolForm({ edit = false }) {
  const { id } = useParams();
  const nav = useNavigate();
  const [types, setTypes] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [typeId, setTypeId] = useState('');
  const [form, setForm] = useState({ name: '', description: '', notes: '', reorderMin: '', attributes: {} });
  const [invRows, setInvRows] = useState([{ locationId: '', quantity: '' }]);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    Promise.all([api('/tool-types'), api('/departments')])
      .then(([t, d]) => { setTypes(t); setDepartments(d); });
  }, []);
  useEffect(() => {
    if (!edit) return;
    api(`/tools/${id}`).then(t => {
      setTypeId(String(t.typeId));
      setForm({ name: t.name, description: t.description, notes: t.notes,
        reorderMin: t.reorderMin ?? '', attributes: t.attributes });
      setInvRows(t.inventory.length
        ? t.inventory.map(l => ({ locationId: String(l.locationId), quantity: String(l.quantity) }))
        : [{ locationId: '', quantity: '' }]);
    }).catch(e => setError(e.message));
  }, [edit, id]);

  const type = types.find(t => String(t.id) === typeId);
  const schema = type?.attributeSchema ?? [];

  const submit = async e => {
    e.preventDefault();
    setError(''); setSaved(false);
    const inventory = invRows
      .filter(r => r.locationId && r.quantity !== '')
      .map(r => ({ locationId: Number(r.locationId), quantity: Number(r.quantity) }));
    const body = { ...form, toolTypeId: Number(typeId), inventory };
    try {
      if (edit) {
        await api(`/tools/${id}`, { method: 'PATCH', body });
        await api(`/tools/${id}/inventory`, { method: 'PUT', body: { inventory } });
        nav(`/tools/${id}`);
      } else {
        const created = await api('/tools', { method: 'POST', body });
        nav(`/tools/${created.id}`);
      }
    } catch (err) {
      setError(err.fields
        ? Object.entries(err.fields).map(([k, v]) => `${k}: ${v}`).join('; ')
        : err.message);
    }
  };

  const F = 'border border-slate-300 rounded-lg px-3 py-2 w-full';
  return (
    <form onSubmit={submit} className="space-y-4 max-w-3xl">
      <h1 className="text-2xl font-bold text-slate-800">{edit ? 'Edit tool' : 'Add tool'}</h1>
      <div className="bg-white shadow rounded-lg p-6 space-y-4">
        <div>
          <label className="block text-sm text-slate-600 mb-1">Tool type</label>
          <select value={typeId} onChange={e => { setTypeId(e.target.value); setForm(f => ({ ...f, attributes: {} })); }}
            className={F} required>
            <option value="">— pick a type —</option>
            {types.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-slate-600 mb-1">Name *</label>
            <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} className={F} required />
          </div>
          <div>
            <label className="block text-sm text-slate-600 mb-1">Description</label>
            <input value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} className={F} />
          </div>
        </div>
        {schema.length > 0 && (
          <fieldset className="border border-slate-200 rounded-lg p-4">
            <legend className="text-sm font-medium text-slate-600 px-1">Attributes — {type.name}</legend>
            <div className="grid grid-cols-2 gap-4">
              {schema.map(f => (
                <div key={f.key}>
                  <label className="block text-sm text-slate-600 mb-1">{f.label}</label>
                  <input type={f.type === 'number' ? 'number' : 'text'} step="any"
                    value={form.attributes[f.key] ?? ''}
                    onChange={e => setForm(f0 => ({ ...f0,
                      attributes: { ...f0.attributes, [f.key]: e.target.value } }))}
                    className={F} />
                </div>
              ))}
            </div>
          </fieldset>
        )}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-slate-600 mb-1">Reorder minimum (low-stock alert at or below)</label>
            <input type="number" min="0" value={form.reorderMin}
              onChange={e => setForm({ ...form, reorderMin: e.target.value })} className={F} />
          </div>
          <div>
            <label className="block text-sm text-slate-600 mb-1">Notes</label>
            <input value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} className={F} />
          </div>
        </div>
      </div>

      <div className="bg-white shadow rounded-lg p-6 space-y-3">
        <h2 className="font-medium text-slate-700">Locations & quantities</h2>
        {invRows.map((row, i) => (
          <div key={i} className="flex gap-2 items-center">
            <select value={row.locationId}
              onChange={e => setInvRows(rows => rows.map((r, j) => j === i ? { ...r, locationId: e.target.value } : r))}
              className={F}>
              <option value="">— location —</option>
              {departments.map(d => (
                <optgroup key={d.id} label={d.name}>
                  {d.locations.map(l => <option key={l.id} value={l.id}>{d.name} — {l.name}</option>)}
                </optgroup>
              ))}
            </select>
            <input type="number" min="0" placeholder="Qty" value={row.quantity}
              onChange={e => setInvRows(rows => rows.map((r, j) => j === i ? { ...r, quantity: e.target.value } : r))}
              className={`${F} w-24`} />
            <button type="button" onClick={() => setInvRows(rows => rows.filter((_, j) => j !== i))}
              className="no-print text-slate-400 hover:text-red-600 px-2 text-lg">×</button>
          </div>
        ))}
        <button type="button"
          onClick={() => setInvRows(rows => [...rows, { locationId: '', quantity: '' }])}
          className="no-print text-sky-600 hover:underline text-sm">+ Add another location</button>
      </div>

      {error && <p className="text-red-600 text-sm">{error}</p>}
      {saved && <p className="text-emerald-600 text-sm">Saved.</p>}
      <div className="flex gap-2">
        <button className="bg-sky-600 hover:bg-sky-500 text-white rounded-lg px-6 py-2 font-medium">
          {edit ? 'Save changes' : 'Add tool'}
        </button>
        <button type="button" onClick={() => nav(-1)} className="no-print text-slate-500 hover:underline">Cancel</button>
      </div>
    </form>
  );
}

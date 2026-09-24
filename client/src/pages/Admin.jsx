import { useEffect, useState } from 'react';
import { api } from '../api.js';

const Btn = 'bg-sky-600 hover:bg-sky-500 text-white rounded-lg px-3 py-1.5 text-sm';
const F = 'border border-slate-300 rounded-lg px-3 py-1.5 text-sm';

function Tab({ label, active, onClick }) {
  return <button onClick={onClick}
    className={`px-4 py-2 rounded-t-lg text-sm font-medium ${active ? 'bg-white text-sky-700 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}>{label}</button>;
}

const deriveKey = label => label.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');

function AttributeRow({ onAdd, addLabel = 'Add' }) {
  const [label, setLabel] = useState('');
  const [type, setType] = useState('text');
  return (
    <div className="flex gap-2 items-center">
      <input value={label} onChange={e => setLabel(e.target.value)} placeholder="Attribute label (e.g. Diameter (mm))" className={F} />
      <select value={type} onChange={e => setType(e.target.value)} className={F + ' w-32'}>
        <option value="text">Text</option>
        <option value="number">Number</option>
      </select>
      <button className={Btn} onClick={() => { if (label.trim()) { onAdd({ label: label.trim(), type }); setLabel(''); } }}>{addLabel}</button>
    </div>
  );
}

function Employees() {
  const [list, setList] = useState([]);
  const [q, setQ] = useState('');
  const [badgeId, setBadgeId] = useState('');
  const [name, setName] = useState('');
  const [paste, setPaste] = useState('');
  const [msg, setMsg] = useState('');
  const load = () => api(`/employees?q=${encodeURIComponent(q)}`).then(setList).catch(() => {});
  useEffect(() => { load(); }, [q]);

  const parsePaste = () => paste.split(/\r?\n/).map(line => {
    const [b, ...rest] = line.split(',');
    return { badgeId: (b ?? '').trim(), name: rest.join(',').trim() };
  }).filter(r => r.badgeId && r.name);

  return (
    <div className="space-y-6">
      <div className="bg-white shadow rounded-lg p-6 space-y-3">
        <h2 className="font-medium text-slate-700">Add employee</h2>
        <div className="flex gap-2">
          <input value={badgeId} onChange={e => setBadgeId(e.target.value)} placeholder="Employee ID" className={F} />
          <input value={name} onChange={e => setName(e.target.value)} placeholder="Name" className={F} />
          <button className={Btn} onClick={async () => {
            setMsg('');
            try { await api('/employees', { method: 'POST', body: { badgeId, name } }); setBadgeId(''); setName(''); load(); }
            catch (e) { setMsg(e.message); }
          }}>Add</button>
        </div>
      </div>
      <div className="bg-white shadow rounded-lg p-6 space-y-3">
        <h2 className="font-medium text-slate-700">Bulk import users</h2>
        <p className="text-sm text-slate-500">Paste lines of <code>EmployeeID,Name</code> (e.g. from Excel).</p>
        <textarea value={paste} onChange={e => setPaste(e.target.value)} rows={4}
          className={`${F} w-full font-mono`} placeholder={'102,Jane Doe\nE106,John Doe\n1104,Bob Smith'} />
        <button className={Btn} onClick={async () => {
          setMsg('');
          try { const r = await api('/employees/import', { method: 'POST', body: { rows: parsePaste() } });
            setMsg(`Imported ${r.imported}, skipped ${r.skipped}.`); setPaste(''); load(); }
          catch (e) { setMsg(e.message); }
        }}>Add Users</button>
      </div>
      <div className="bg-white shadow rounded-lg p-6 space-y-3">
        <h2 className="font-medium text-slate-700">Employees</h2>
        <input value={q} onChange={e => setQ(e.target.value)} placeholder="Filter…" className={F} />
        <ul className="text-sm divide-y divide-slate-100">
          {list.map(emp => (
            <li key={emp.badgeId} className="flex items-center gap-3 py-1.5">
              <span className={!emp.active ? 'text-slate-400 line-through' : ''}>
                {emp.name} ({emp.badgeId}){emp.isAdmin ? ' [admin]' : ''}
              </span>
              <button className="ml-auto text-sky-600 hover:underline text-xs" onClick={async () => {
                setMsg('');
                try { await api(`/employees/${emp.badgeId}`, { method: 'PATCH', body: { active: !emp.active } }); load(); }
                catch (e) { setMsg(e.message); }
              }}>{emp.active ? 'Deactivate' : 'Reactivate'}</button>
              <button className="text-amber-600 hover:underline text-xs" onClick={async () => {
                setMsg('');
                try { await api(`/employees/${emp.badgeId}`, { method: 'PATCH', body: { isAdmin: !emp.isAdmin } }); load(); }
                catch (e) { setMsg(e.message); }
              }}>{emp.isAdmin ? 'Remove admin' : 'Make admin'}</button>
            </li>
          ))}
        </ul>
      </div>
      {msg && <p className="text-sm text-slate-600">{msg}</p>}
    </div>
  );
}

function Departments() {
  const [departments, setDepartments] = useState([]);
  const [deptName, setDeptName] = useState('');
  const [locBy, setLocBy] = useState({});
  const load = () => api('/departments').then(setDepartments).catch(e => alert(e.message));
  useEffect(() => { load(); }, []);
  return (
    <div className="space-y-6">
      <div className="bg-white shadow rounded-lg p-6 flex gap-2 items-end">
        <div><label className="block text-sm text-slate-600 mb-1">New department</label>
          <input value={deptName} onChange={e => setDeptName(e.target.value)} className={F} /></div>
        <button className={Btn} onClick={async () => {
          try { await api('/departments', { method: 'POST', body: { name: deptName } }); setDeptName(''); load(); }
          catch (e) { alert(e.message); }
        }}>Add department</button>
      </div>
      {departments.map(d => (
        <div key={d.id} className="bg-white shadow rounded-lg p-6">
          <div className="flex items-center gap-3">
            <h2 className="font-medium text-slate-700">{d.name}</h2>
            <button className="text-sky-600 hover:underline text-xs" onClick={async () => {
              const name = prompt(`Rename department "${d.name}" to:`, d.name);
              if (!name || name === d.name) return;
              try { await api(`/departments/${d.id}`, { method: 'PATCH', body: { name } }); load(); }
              catch (e) { alert(e.message); }
            }}>rename</button>
            <button className="text-red-600 hover:underline text-xs" onClick={async () => {
              if (!confirm(`Delete department "${d.name}"? Only possible when it has no locations.`)) return;
              try { await api(`/departments/${d.id}`, { method: 'DELETE' }); load(); }
              catch (e) { alert(e.message); }
            }}>delete</button>
          </div>
          <ul className="text-sm my-2 space-y-1">
            {d.locations.map(l => (
              <li key={l.id} className="flex gap-2 items-center">
                {l.name}
                <button className="text-sky-600 hover:underline text-xs" onClick={async () => {
                  const name = prompt(`Rename location "${l.name}" to:`, l.name);
                  if (!name || name === l.name) return;
                  try { await api(`/locations/${l.id}`, { method: 'PATCH', body: { name } }); load(); }
                  catch (e) { alert(e.message); }
                }}>rename</button>
                <button className="text-red-600 hover:underline text-xs" onClick={async () => {
                  try { await api(`/locations/${l.id}`, { method: 'DELETE' }); load(); }
                  catch (e) { alert(e.message); }
                }}>remove</button>
              </li>
            ))}
            {d.locations.length === 0 && <li className="text-slate-400">No locations yet.</li>}
          </ul>
          <div className="flex gap-2">
            <input value={locBy[d.id] ?? ''} onChange={e => setLocBy(m => ({ ...m, [d.id]: e.target.value }))}
              placeholder="New location name" className={F} />
            <button className={Btn} onClick={async () => {
              try { await api('/locations', { method: 'POST', body: { departmentId: d.id, name: locBy[d.id] } });
                setLocBy(m => ({ ...m, [d.id]: '' })); load(); }
              catch (e) { alert(e.message); }
            }}>Add location</button>
          </div>
        </div>
      ))}
    </div>
  );
}

function ToolTypes() {
  const [types, setTypes] = useState([]);
  const [name, setName] = useState('');
  const [rows, setRows] = useState([]); // [{key, label, type}] for the new type
  const load = () => api('/tool-types').then(setTypes).catch(e => alert(e.message));
  useEffect(() => { load(); }, []);
  return (
    <div className="space-y-6">
      <div className="bg-white shadow rounded-lg p-6 space-y-3">
        <h2 className="font-medium text-slate-700">New tool type</h2>
        <input value={name} onChange={e => setName(e.target.value)} placeholder="Type name (e.g. Dressing diamonds)" className={F} />
        <ul className="text-sm space-y-1">
          {rows.map((f, i) => (
            <li key={f.key + i} className="flex gap-2 items-center">
              {f.label} <span className="text-slate-400">({f.type})</span>
              <span className="text-slate-400 font-mono text-xs">{f.key}</span>
              <button className="ml-auto text-red-600 hover:underline text-xs"
                onClick={() => setRows(rs => rs.filter((_, j) => j !== i))}>remove</button>
            </li>
          ))}
        </ul>
        <AttributeRow onAdd={f => setRows(rs => [...rs, { key: deriveKey(f.label), label: f.label, type: f.type }])} />
        <button className={Btn} onClick={async () => {
          try { await api('/tool-types', { method: 'POST', body: { name, attributeSchema: rows } });
            setName(''); setRows([]); load(); }
          catch (e) { alert(e.message); }
        }}>Create type</button>
      </div>
      {types.map(t => (
        <div key={t.id} className="bg-white shadow rounded-lg p-6">
          <div className="flex items-center gap-3">
            <h2 className="font-medium text-slate-700">{t.name}</h2>
            <button className="text-sky-600 hover:underline text-xs" onClick={async () => {
              const name = prompt(`Rename tool type "${t.name}" to:`, t.name);
              if (!name || name === t.name) return;
              try { await api(`/tool-types/${t.id}`, { method: 'PATCH', body: { name } }); load(); }
              catch (e) { alert(e.message); }
            }}>rename</button>
            <button className="ml-auto text-red-600 hover:underline text-xs"
              onClick={async () => {
                if (!confirm(`Remove tool type "${t.name}"? Only possible when no tools use it.`)) return;
                try { await api(`/tool-types/${t.id}`, { method: 'DELETE' }); load(); }
                catch (e) { alert(e.message); }
              }}>remove type</button>
          </div>
          <ul className="text-sm my-2 space-y-1">
            {t.attributeSchema.map((f, i) => (
              <li key={f.key + i} className="flex gap-2 items-center">
                {f.label} <span className="text-slate-400">({f.type})</span>
                <button className="text-red-600 hover:underline text-xs" onClick={async () => {
                  try { await api(`/tool-types/${t.id}`, { method: 'PATCH',
                    body: { attributeSchema: t.attributeSchema.filter(x => x.key !== f.key) } }); load(); }
                  catch (e) { alert(e.message); }
                }}>remove</button>
              </li>
            ))}
            {t.attributeSchema.length === 0 && <li className="text-slate-400">No attributes.</li>}
          </ul>
          <AttributeRow addLabel="Add attribute" onAdd={async f => {
            try { await api(`/tool-types/${t.id}`, { method: 'PATCH',
              body: { attributeSchema: [...t.attributeSchema,
                { key: deriveKey(f.label), label: f.label, type: f.type }] } });
              load(); }
            catch (e) { alert(e.message); }
          }} />
        </div>
      ))}
    </div>
  );
}

export default function Admin() {
  const [tab, setTab] = useState('employees');
  return (
    <div className="space-y-4">
      <div className="flex gap-1 border-b border-slate-200">
        <Tab label="Employees" active={tab === 'employees'} onClick={() => setTab('employees')} />
        <Tab label="Departments & locations" active={tab === 'departments'} onClick={() => setTab('departments')} />
        <Tab label="Tool types" active={tab === 'tooltypes'} onClick={() => setTab('tooltypes')} />
      </div>
      {tab === 'employees' && <Employees />}
      {tab === 'departments' && <Departments />}
      {tab === 'tooltypes' && <ToolTypes />}
      <div className="bg-white shadow rounded-lg p-6 no-print">
        <h2 className="font-medium text-slate-700 mb-2">Backup</h2>
        <a href="/api/backup" className={Btn + ' inline-block'}>Download database backup</a>
      </div>
    </div>
  );
}

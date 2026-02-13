import { useState, useEffect } from 'react';
import { apiGet, apiPost, apiPatch, apiDelete } from '../api/client';

const EVENT_TYPES = ['new_moon', 'full_moon', 'lunar_eclipse', 'solar_eclipse', 'retrograde_station', 'direct_station', 'ingress_major'];

export default function EventsPage() {
  const [events, setEvents] = useState<any[]>([]);
  const [showAdd, setShowAdd] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [form, setForm] = useState({ event_type: 'new_moon', body: '', sign: '', at: '', significance: 'moderate' });

  useEffect(() => { loadEvents(); }, []);

  async function loadEvents() {
    apiGet('/admin/events/').then(setEvents).catch(() => {});
  }

  async function handleAdd() {
    await apiPost('/admin/events/', form);
    setShowAdd(false);
    loadEvents();
  }

  async function handleEdit(id: string) {
    await apiPatch(`/admin/events/${id}`, form);
    setEditing(null);
    loadEvents();
  }

  async function handleDelete(id: string) {
    await apiDelete(`/admin/events/${id}`);
    setEvents(events.filter((e) => e.id !== id));
  }

  async function handleGenerateReading(id: string) {
    await apiPost(`/admin/events/${id}/generate-reading`, {});
    loadEvents();
  }

  function startEdit(e: any) {
    setEditing(e.id);
    setForm({ event_type: e.event_type, body: e.body || '', sign: e.sign || '', at: e.at?.slice(0, 16) || '', significance: e.significance });
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-xl text-accent">Astronomical Events</h1>
        <button onClick={() => setShowAdd(!showAdd)} className="text-xs px-3 py-1 bg-surface-raised border border-text-ghost rounded text-accent hover:border-accent">
          + Add Event
        </button>
      </div>

      {showAdd && (
        <div className="bg-surface-raised border border-text-ghost rounded p-4 mb-4 space-y-2">
          <div className="grid grid-cols-5 gap-2">
            <select value={form.event_type} onChange={(e) => setForm({ ...form, event_type: e.target.value })} className="bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary">
              {EVENT_TYPES.map((t) => <option key={t}>{t.replace(/_/g, ' ')}</option>)}
            </select>
            <input placeholder="Body" value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary" />
            <input placeholder="Sign" value={form.sign} onChange={(e) => setForm({ ...form, sign: e.target.value })} className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary" />
            <input type="datetime-local" value={form.at} onChange={(e) => setForm({ ...form, at: e.target.value })} className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary" />
            <select value={form.significance} onChange={(e) => setForm({ ...form, significance: e.target.value })} className="bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary">
              <option>major</option><option>moderate</option><option>minor</option>
            </select>
          </div>
          <button onClick={handleAdd} className="text-xs px-3 py-1 bg-accent/20 text-accent rounded">Save</button>
        </div>
      )}

      <div className="space-y-2">
        {events.map((e) => (
          <div key={e.id} className="bg-surface-raised border border-text-ghost rounded p-3">
            {editing === e.id ? (
              <div className="space-y-2">
                <div className="grid grid-cols-5 gap-2">
                  <select value={form.event_type} onChange={(ev) => setForm({ ...form, event_type: ev.target.value })} className="bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary">
                    {EVENT_TYPES.map((t) => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}
                  </select>
                  <input value={form.body} onChange={(ev) => setForm({ ...form, body: ev.target.value })} className="bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary" />
                  <input value={form.sign} onChange={(ev) => setForm({ ...form, sign: ev.target.value })} className="bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary" />
                  <input type="datetime-local" value={form.at} onChange={(ev) => setForm({ ...form, at: ev.target.value })} className="bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary" />
                  <select value={form.significance} onChange={(ev) => setForm({ ...form, significance: ev.target.value })} className="bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary">
                    <option>major</option><option>moderate</option><option>minor</option>
                  </select>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => handleEdit(e.id)} className="text-xs px-2 py-1 bg-accent/20 text-accent rounded">Save</button>
                  <button onClick={() => setEditing(null)} className="text-xs px-2 py-1 text-text-muted">Cancel</button>
                </div>
              </div>
            ) : (
              <div className="flex justify-between items-center">
                <div>
                  <span className="text-sm text-text-primary">{e.event_type.replace(/_/g, ' ')}</span>
                  {e.body && <span className="text-xs text-text-secondary ml-2">{e.body}</span>}
                  {e.sign && <span className="text-xs text-text-muted ml-1">in {e.sign}</span>}
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-text-muted">{new Date(e.at).toLocaleDateString()}</span>
                  <span className={`text-xs ${e.significance === 'major' ? 'text-accent' : 'text-text-muted'}`}>{e.significance}</span>
                  <span className={`text-xs ${e.reading_status === 'generated' ? 'text-green-400' : 'text-text-muted'}`}>{e.reading_status}</span>
                  <button onClick={() => handleGenerateReading(e.id)} className="text-xs text-accent hover:underline">generate</button>
                  <button onClick={() => startEdit(e)} className="text-xs text-text-muted hover:text-accent">edit</button>
                  <button onClick={() => handleDelete(e.id)} className="text-xs text-red-400 hover:text-red-300">delete</button>
                </div>
              </div>
            )}
          </div>
        ))}
        {events.length === 0 && <p className="text-text-muted text-sm">No events.</p>}
      </div>
    </div>
  );
}

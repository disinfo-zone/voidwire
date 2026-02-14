import { useState, useEffect } from 'react';
import { apiGet, apiPost, apiPatch, apiDelete } from '../api/client';
import { useToast } from '../components/ui/ToastProvider';
import ConfirmDialog from '../components/ui/ConfirmDialog';
import Spinner from '../components/ui/Spinner';

const EVENT_TYPES = ['new_moon', 'full_moon', 'lunar_eclipse', 'solar_eclipse', 'retrograde_station', 'direct_station', 'ingress_major'];

export default function EventsPage() {
  const [events, setEvents] = useState<any[]>([]);
  const [showAdd, setShowAdd] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [form, setForm] = useState({ event_type: 'new_moon', body: '', sign: '', at: '', significance: 'moderate' });
  const [loading, setLoading] = useState(true);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const { toast } = useToast();

  useEffect(() => { loadEvents(); }, []);

  async function loadEvents() {
    setLoading(true);
    try {
      const data = await apiGet('/admin/events/');
      setEvents(data);
    } catch (e: any) {
      toast.error(e.message);
    }
    setLoading(false);
  }

  async function handleAdd() {
    try {
      await apiPost('/admin/events/', form);
      setShowAdd(false);
      loadEvents();
      toast.success('Event created');
    } catch (e: any) {
      toast.error(e.message);
    }
  }

  async function handleEdit(id: string) {
    try {
      await apiPatch(`/admin/events/${id}`, form);
      setEditing(null);
      loadEvents();
      toast.success('Event updated');
    } catch (e: any) {
      toast.error(e.message);
    }
  }

  async function confirmDelete() {
    if (!deleteId) return;
    try {
      await apiDelete(`/admin/events/${deleteId}`);
      setEvents(events.filter((e) => e.id !== deleteId));
      toast.success('Event deleted');
    } catch (e: any) {
      toast.error(e.message);
    }
    setDeleteId(null);
  }

  async function handleGenerateReading(id: string) {
    try {
      await apiPost(`/admin/events/${id}/generate-reading`, {});
      toast.success('Reading generation started');
      loadEvents();
    } catch (e: any) {
      toast.error(e.message);
    }
  }

  function startEdit(e: any) {
    setEditing(e.id);
    setForm({ event_type: e.event_type, body: e.body || '', sign: e.sign || '', at: e.at?.slice(0, 16) || '', significance: e.significance });
  }

  if (loading) return <div><h1 className="text-xl mb-6 text-accent">Astronomical Events</h1><div className="flex justify-center py-12"><Spinner /></div></div>;

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-xl text-accent">Astronomical Events</h1>
        <button onClick={() => setShowAdd(!showAdd)} className="text-xs px-3 py-1 bg-surface-raised border border-text-ghost rounded text-accent hover:border-accent">
          + Add Event
        </button>
      </div>

      <div className="bg-surface-raised border border-text-ghost rounded p-4 mb-4 space-y-2 text-xs">
        <h2 className="text-sm text-text-primary">Quick Guide</h2>
        <div className="text-text-muted">
          Use this page to curate major sky events and optionally trigger a focused reading for that event date.
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          <div className="bg-surface border border-text-ghost rounded px-3 py-2">
            <div className="text-text-secondary mb-1">When To Add</div>
            <div className="text-text-muted">
              Add eclipses, lunations, retrograde/direct stations, and major ingresses you want to highlight editorially.
            </div>
          </div>
          <div className="bg-surface border border-text-ghost rounded px-3 py-2">
            <div className="text-text-secondary mb-1">Field Tips</div>
            <div className="text-text-muted">
              <span className="font-mono">at</span> uses local datetime input.
              <span className="ml-1 font-mono">significance</span> controls editorial priority (major/moderate/minor).
            </div>
          </div>
          <div className="bg-surface border border-text-ghost rounded px-3 py-2">
            <div className="text-text-secondary mb-1">Generate</div>
            <div className="text-text-muted">
              <span className="font-mono">generate</span> runs the pipeline for that event date. It does not auto-publish unless auto-publish is enabled.
            </div>
          </div>
          <div className="bg-surface border border-text-ghost rounded px-3 py-2">
            <div className="text-text-secondary mb-1">Publishing</div>
            <div className="text-text-muted">
              Public site endpoints only show readings with status <span className="font-mono">published</span>. Review and publish from Readings if auto-publish is off.
            </div>
          </div>
        </div>
      </div>

      {showAdd && (
        <div className="bg-surface-raised border border-text-ghost rounded p-4 mb-4 space-y-2">
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
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
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
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
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
                <div>
                  <span className="text-sm text-text-primary">{e.event_type.replace(/_/g, ' ')}</span>
                  {e.body && <span className="text-xs text-text-secondary ml-2">{e.body}</span>}
                  {e.sign && <span className="text-xs text-text-muted ml-1">in {e.sign}</span>}
                </div>
                <div className="flex items-center gap-3 flex-wrap">
                  <span className="text-xs text-text-muted">{new Date(e.at).toLocaleDateString()}</span>
                  <span className={`text-xs ${e.significance === 'major' ? 'text-accent' : 'text-text-muted'}`}>{e.significance}</span>
                  <span className={`text-xs ${e.reading_status === 'generated' ? 'text-green-400' : 'text-text-muted'}`}>{e.reading_status}</span>
                  <button onClick={() => handleGenerateReading(e.id)} className="text-xs text-accent hover:underline">generate</button>
                  <button onClick={() => startEdit(e)} className="text-xs text-text-muted hover:text-accent">edit</button>
                  <button onClick={() => setDeleteId(e.id)} className="text-xs text-red-400 hover:text-red-300">delete</button>
                </div>
              </div>
            )}
          </div>
        ))}
        {events.length === 0 && <p className="text-text-muted text-sm">No events.</p>}
      </div>

      <ConfirmDialog
        open={!!deleteId}
        title="Delete Event"
        message="Are you sure you want to delete this event?"
        onConfirm={confirmDelete}
        onCancel={() => setDeleteId(null)}
        destructive
      />
    </div>
  );
}

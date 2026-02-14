import { useState, useEffect } from 'react';
import { apiGet, apiPatch, apiDelete } from '../api/client';
import { useToast } from '../components/ui/ToastProvider';
import ConfirmDialog from '../components/ui/ConfirmDialog';
import Spinner from '../components/ui/Spinner';

const DOMAINS = ['conflict', 'diplomacy', 'economy', 'technology', 'culture', 'environment', 'social', 'anomalous', 'legal', 'health'];

export default function ThreadsPage() {
  const [threads, setThreads] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);
  const [signals, setSignals] = useState<any[]>([]);
  const [filters, setFilters] = useState({ active: '', domain: '', page: 1 });
  const [editing, setEditing] = useState(false);
  const [editForm, setEditForm] = useState({ canonical_summary: '', domain: '', active: true });
  const [loading, setLoading] = useState(true);
  const [confirmAction, setConfirmAction] = useState<{ id: string; active: boolean } | null>(null);
  const { toast } = useToast();

  useEffect(() => { loadThreads(); }, []);

  async function loadThreads() {
    setLoading(true);
    const params = new URLSearchParams();
    if (filters.active) params.set('active', filters.active);
    if (filters.domain) params.set('domain', filters.domain);
    params.set('page', String(filters.page));
    const qs = params.toString();
    try {
      const data = await apiGet(`/admin/threads/${qs ? '?' + qs : ''}`);
      setThreads(data);
    } catch (e: any) {
      toast.error(e.message);
    }
    setLoading(false);
  }

  async function selectThread(t: any) {
    setSelected(t);
    setEditing(false);
    try {
      const sigs = await apiGet(`/admin/threads/${t.id}/signals`);
      setSignals(sigs);
    } catch { setSignals([]); }
  }

  function startEdit() {
    if (!selected) return;
    setEditForm({
      canonical_summary: selected.canonical_summary || '',
      domain: selected.domain || '',
      active: selected.active,
    });
    setEditing(true);
  }

  async function handleSave() {
    if (!selected) return;
    try {
      await apiPatch(`/admin/threads/${selected.id}`, editForm);
      setEditing(false);
      const updated = { ...selected, ...editForm };
      setSelected(updated);
      setThreads(threads.map((t) => (t.id === selected.id ? updated : t)));
      toast.success('Thread updated');
    } catch (e: any) {
      toast.error(e.message);
    }
  }

  async function handleDeactivate(id: string) {
    try {
      await apiDelete(`/admin/threads/${id}`);
      setThreads(threads.map((t) => (t.id === id ? { ...t, active: false } : t)));
      if (selected?.id === id) setSelected({ ...selected, active: false });
      toast.success('Thread deactivated');
    } catch (e: any) {
      toast.error(e.message);
    }
  }

  async function handleToggleActive(t: any) {
    if (t.active) {
      setConfirmAction({ id: t.id, active: false });
      return;
    }
    try {
      await apiPatch(`/admin/threads/${t.id}`, { active: true });
      setThreads(threads.map((th) => (th.id === t.id ? { ...th, active: true } : th)));
      if (selected?.id === t.id) setSelected({ ...selected, active: true });
      toast.success('Thread reactivated');
    } catch (e: any) {
      toast.error(e.message);
    }
  }

  async function confirmToggle() {
    if (!confirmAction) return;
    try {
      await apiPatch(`/admin/threads/${confirmAction.id}`, { active: confirmAction.active });
      setThreads(threads.map((th) => (th.id === confirmAction.id ? { ...th, active: confirmAction.active } : th)));
      if (selected?.id === confirmAction.id) setSelected({ ...selected, active: confirmAction.active });
      toast.success('Thread deactivated');
    } catch (e: any) {
      toast.error(e.message);
    }
    setConfirmAction(null);
  }

  return (
    <div>
      <h1 className="text-xl mb-6 text-accent">Narrative Threads</h1>

      {/* Filters */}
      <div className="flex gap-2 mb-4 flex-wrap">
        <select value={filters.active} onChange={(e) => setFilters({ ...filters, active: e.target.value, page: 1 })} className="bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary">
          <option value="">All threads</option>
          <option value="true">Active</option>
          <option value="false">Inactive</option>
        </select>
        <select value={filters.domain} onChange={(e) => setFilters({ ...filters, domain: e.target.value, page: 1 })} className="bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary">
          <option value="">All domains</option>
          {DOMAINS.map((d) => <option key={d}>{d}</option>)}
        </select>
        <button onClick={loadThreads} className="text-xs px-3 py-1 bg-accent/20 text-accent rounded">Filter</button>
        <div className="flex-1" />
        <div className="flex gap-1">
          <button onClick={() => { if (filters.page > 1) setFilters({ ...filters, page: filters.page - 1 }); }} disabled={filters.page <= 1} className="text-xs px-2 py-1 text-text-muted disabled:opacity-30">Prev</button>
          <span className="text-xs px-2 py-1 text-text-muted">Page {filters.page}</span>
          <button onClick={() => setFilters({ ...filters, page: filters.page + 1 })} className="text-xs px-2 py-1 text-text-muted">Next</button>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-12"><Spinner /></div>
      ) : (
        <div className="flex flex-col lg:flex-row gap-4">
          {/* Thread list */}
          <div className="w-full lg:w-80 shrink-0 space-y-1 max-h-[calc(100vh-220px)] overflow-auto">
            {threads.map((t) => (
              <div
                key={t.id}
                onClick={() => selectThread(t)}
                className={`bg-surface-raised border rounded p-3 cursor-pointer hover:border-text-muted ${selected?.id === t.id ? 'border-accent' : 'border-text-ghost'}`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className={`w-2 h-2 rounded-full ${t.active ? 'bg-green-400' : 'bg-text-ghost'}`} />
                  <span className="text-xs text-text-muted">{t.domain}</span>
                  {t.signal_count != null && <span className="text-xs text-text-ghost ml-auto">{t.signal_count} signals</span>}
                </div>
                <div className="text-sm text-text-primary line-clamp-2">{t.canonical_summary || 'No summary'}</div>
                <div className="text-xs text-text-ghost mt-1">
                  {t.created_at ? new Date(t.created_at).toLocaleDateString() : ''}
                  {t.last_seen_at && <span className="ml-2">last seen {new Date(t.last_seen_at).toLocaleDateString()}</span>}
                </div>
              </div>
            ))}
            {threads.length === 0 && <p className="text-text-muted text-sm">No threads found.</p>}
          </div>

          {/* Detail panel */}
          {selected && (
            <div className="flex-1 space-y-4">
              <div className="bg-surface-raised border border-text-ghost rounded p-4">
                <div className="flex justify-between items-start mb-3">
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${selected.active ? 'bg-green-400' : 'bg-text-ghost'}`} />
                    <span className="text-xs text-text-muted uppercase tracking-wider">{selected.domain}</span>
                    <span className={`text-xs ${selected.active ? 'text-green-400' : 'text-text-muted'}`}>{selected.active ? 'Active' : 'Inactive'}</span>
                  </div>
                  <div className="flex gap-2">
                    {!editing && <button onClick={startEdit} className="text-xs text-text-muted hover:text-accent">edit</button>}
                    <button onClick={() => handleToggleActive(selected)} className={`text-xs ${selected.active ? 'text-red-400 hover:text-red-300' : 'text-green-400 hover:text-green-300'}`}>
                      {selected.active ? 'deactivate' : 'reactivate'}
                    </button>
                  </div>
                </div>

                {editing ? (
                  <div className="space-y-2">
                    <textarea
                      value={editForm.canonical_summary}
                      onChange={(e) => setEditForm({ ...editForm, canonical_summary: e.target.value })}
                      rows={3}
                      className="w-full bg-surface border border-text-ghost rounded px-3 py-2 text-sm text-text-primary"
                    />
                    <div className="flex gap-2 items-center flex-wrap">
                      <select value={editForm.domain} onChange={(e) => setEditForm({ ...editForm, domain: e.target.value })} className="bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary">
                        {DOMAINS.map((d) => <option key={d}>{d}</option>)}
                      </select>
                      <label className="flex items-center gap-1 text-xs text-text-muted">
                        <input type="checkbox" checked={editForm.active} onChange={(e) => setEditForm({ ...editForm, active: e.target.checked })} />
                        Active
                      </label>
                      <div className="flex-1" />
                      <button onClick={handleSave} className="text-xs px-3 py-1 bg-accent/20 text-accent rounded">Save</button>
                      <button onClick={() => setEditing(false)} className="text-xs px-2 py-1 text-text-muted">Cancel</button>
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-text-primary">{selected.canonical_summary || 'No summary'}</p>
                )}

                <div className="mt-3 flex gap-4 text-xs text-text-ghost flex-wrap">
                  <span>ID: {selected.id?.slice(0, 8)}</span>
                  {selected.created_at && <span>Created: {new Date(selected.created_at).toLocaleDateString()}</span>}
                  {selected.last_seen_at && <span>Last seen: {new Date(selected.last_seen_at).toLocaleDateString()}</span>}
                  {selected.centroid_version != null && <span>Centroid v{selected.centroid_version}</span>}
                </div>
              </div>

              {/* Signal history */}
              <div className="bg-surface-raised border border-text-ghost rounded p-4">
                <h4 className="text-xs text-text-muted uppercase tracking-wider mb-3">Signal History ({signals.length})</h4>
                <div className="space-y-1 max-h-96 overflow-auto">
                  {signals.map((s) => (
                    <div key={s.id} className="bg-surface rounded p-2 flex justify-between items-start text-xs">
                      <div className="flex-1 mr-3">
                        <div className="text-text-primary">{s.summary || s.headline}</div>
                        <div className="flex gap-2 mt-1">
                          <span className="text-text-muted">{s.domain}</span>
                          <span className={`${s.intensity === 'major' ? 'text-accent' : 'text-text-muted'}`}>{s.intensity}</span>
                          {s.selected && <span className="text-green-400">selected</span>}
                        </div>
                      </div>
                      <span className="text-text-ghost shrink-0">{s.created_at ? new Date(s.created_at).toLocaleDateString() : ''}</span>
                    </div>
                  ))}
                  {signals.length === 0 && <p className="text-text-muted text-sm">No signals associated with this thread.</p>}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      <ConfirmDialog
        open={!!confirmAction}
        title="Deactivate Thread"
        message="Are you sure you want to deactivate this thread?"
        onConfirm={confirmToggle}
        onCancel={() => setConfirmAction(null)}
        destructive
      />
    </div>
  );
}

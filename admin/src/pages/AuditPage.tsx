import { useState, useEffect } from 'react';
import { apiGet } from '../api/client';
import { useToast } from '../components/ui/ToastProvider';
import Spinner from '../components/ui/Spinner';

export default function AuditPage() {
  const [entries, setEntries] = useState<any[]>([]);
  const [filters, setFilters] = useState({ action: '', target_type: '', date_from: '', date_to: '' });
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();

  useEffect(() => { loadAudit(); }, []);

  async function loadAudit() {
    setLoading(true);
    const params = new URLSearchParams();
    if (filters.action) params.set('action', filters.action);
    if (filters.target_type) params.set('target_type', filters.target_type);
    if (filters.date_from) params.set('date_from', filters.date_from);
    if (filters.date_to) params.set('date_to', filters.date_to);
    const qs = params.toString();
    try {
      const data = await apiGet(`/admin/audit/${qs ? '?' + qs : ''}`);
      setEntries(data);
    } catch (e: any) {
      toast.error(e.message);
    }
    setLoading(false);
  }

  return (
    <div>
      <h1 className="text-xl mb-6 text-accent">Audit Log</h1>
      <div className="bg-surface-raised border border-text-ghost rounded p-3 mb-4 text-xs space-y-1">
        <div className="text-text-primary">Quick Guide</div>
        <div className="text-text-muted">
          This view shows the latest 50 admin/system actions (newest first).
          Use filters to narrow by action (for example <span className="font-mono">pipeline.trigger</span>, <span className="font-mono">source.create</span>, <span className="font-mono">reading.published</span>).
        </div>
        <div className="text-text-muted">
          If no entries appear, perform an admin action and click <span className="font-mono">Filter</span> to refresh.
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-2 mb-4 flex-wrap">
        <input placeholder="Action" value={filters.action} onChange={(e) => setFilters({ ...filters, action: e.target.value })} className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary" />
        <select value={filters.target_type} onChange={(e) => setFilters({ ...filters, target_type: e.target.value })} className="bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary">
          <option value="">All targets</option>
          <option value="reading">reading</option>
          <option value="source">source</option>
          <option value="template">template</option>
          <option value="event">event</option>
          <option value="setting">setting</option>
          <option value="llm">llm</option>
          <option value="pipeline">pipeline</option>
          <option value="auth">auth</option>
          <option value="system">system</option>
        </select>
        <input type="date" value={filters.date_from} onChange={(e) => setFilters({ ...filters, date_from: e.target.value })} className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary" />
        <input type="date" value={filters.date_to} onChange={(e) => setFilters({ ...filters, date_to: e.target.value })} className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary" />
        <button onClick={loadAudit} className="text-xs px-3 py-1 bg-accent/20 text-accent rounded">Filter</button>
      </div>

      {loading ? (
        <div className="flex justify-center py-12"><Spinner /></div>
      ) : (
        <div className="space-y-1">
          {entries.map((e) => (
            <div key={e.id} className="bg-surface-raised border border-text-ghost rounded p-2 flex flex-col sm:flex-row justify-between text-xs gap-1">
              <div className="flex items-center gap-3 flex-wrap">
                <span className="text-accent">{e.action}</span>
                {e.target_type && <span className="text-text-muted">{e.target_type}</span>}
                {e.target_id && <span className="text-text-ghost font-mono">{e.target_id.slice(0, 8)}</span>}
                {e.user_id && <span className="text-text-ghost">user:{e.user_id.slice(0, 8)}</span>}
                {e.ip_address && <span className="text-text-ghost">{e.ip_address}</span>}
              </div>
              <div className="flex items-center gap-2">
                {e.detail && (
                  <details className="inline">
                    <summary className="cursor-pointer text-text-muted">detail</summary>
                    <pre className="text-xs text-text-secondary mt-1">{JSON.stringify(e.detail, null, 2)}</pre>
                  </details>
                )}
                <span className="text-text-muted">{e.created_at ? new Date(e.created_at).toLocaleString() : ''}</span>
              </div>
            </div>
          ))}
          {entries.length === 0 && <p className="text-text-muted text-sm">No audit entries.</p>}
        </div>
      )}
    </div>
  );
}

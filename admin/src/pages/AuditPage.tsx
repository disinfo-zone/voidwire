import { useState, useEffect } from 'react';
import { apiGet } from '../api/client';

export default function AuditPage() {
  const [entries, setEntries] = useState<any[]>([]);
  const [filters, setFilters] = useState({ action: '', target_type: '', date_from: '', date_to: '' });

  useEffect(() => { loadAudit(); }, []);

  async function loadAudit() {
    const params = new URLSearchParams();
    if (filters.action) params.set('action', filters.action);
    if (filters.target_type) params.set('target_type', filters.target_type);
    if (filters.date_from) params.set('date_from', filters.date_from);
    if (filters.date_to) params.set('date_to', filters.date_to);
    const qs = params.toString();
    apiGet(`/admin/audit/${qs ? '?' + qs : ''}`).then(setEntries).catch(() => {});
  }

  return (
    <div>
      <h1 className="text-xl mb-6 text-accent">Audit Log</h1>

      {/* Filters */}
      <div className="flex gap-2 mb-4">
        <input placeholder="Action" value={filters.action} onChange={(e) => setFilters({ ...filters, action: e.target.value })} className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary" />
        <select value={filters.target_type} onChange={(e) => setFilters({ ...filters, target_type: e.target.value })} className="bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary">
          <option value="">All targets</option>
          <option value="reading">reading</option>
          <option value="source">source</option>
          <option value="template">template</option>
          <option value="event">event</option>
          <option value="setting">setting</option>
        </select>
        <input type="date" value={filters.date_from} onChange={(e) => setFilters({ ...filters, date_from: e.target.value })} className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary" />
        <input type="date" value={filters.date_to} onChange={(e) => setFilters({ ...filters, date_to: e.target.value })} className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary" />
        <button onClick={loadAudit} className="text-xs px-3 py-1 bg-accent/20 text-accent rounded">Filter</button>
      </div>

      <div className="space-y-1">
        {entries.map((e) => (
          <div key={e.id} className="bg-surface-raised border border-text-ghost rounded p-2 flex justify-between text-xs">
            <div className="flex items-center gap-3">
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
    </div>
  );
}

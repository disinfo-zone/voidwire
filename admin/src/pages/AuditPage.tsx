import { useState, useEffect } from 'react';
import { apiGet } from '../api/client';

export default function AuditPage() {
  const [entries, setEntries] = useState<any[]>([]);

  useEffect(() => {
    apiGet('/admin/audit/').then(setEntries).catch(() => {});
  }, []);

  return (
    <div>
      <h1 className="text-xl mb-6 text-accent">Audit Log</h1>
      <div className="space-y-1">
        {entries.map(e => (
          <div key={e.id} className="bg-surface-raised border border-text-ghost rounded p-2 flex justify-between text-xs">
            <div>
              <span className="text-accent">{e.action}</span>
              {e.target_type && <span className="text-text-muted ml-2">{e.target_type}</span>}
            </div>
            <span className="text-text-muted">{e.created_at ? new Date(e.created_at).toLocaleString() : ''}</span>
          </div>
        ))}
        {entries.length === 0 && <p className="text-text-muted text-sm">No audit entries.</p>}
      </div>
    </div>
  );
}

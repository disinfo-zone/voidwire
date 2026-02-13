import { useState, useEffect } from 'react';
import { apiGet, apiPatch } from '../api/client';

export default function ReadingsPage() {
  const [readings, setReadings] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);

  useEffect(() => {
    apiGet('/admin/readings/').then(setReadings).catch(() => {});
  }, []);

  async function handleStatusChange(id: string, status: string) {
    await apiPatch(`/admin/readings/${id}`, { status });
    setReadings(readings.map(r => r.id === id ? { ...r, status } : r));
  }

  return (
    <div>
      <h1 className="text-xl mb-6 text-accent">Readings</h1>

      <div className="space-y-2">
        {readings.map((r) => (
          <div
            key={r.id}
            className="bg-surface-raised border border-text-ghost rounded p-4 flex items-center justify-between cursor-pointer hover:border-text-muted"
            onClick={() => setSelected(r)}
          >
            <div>
              <span className="text-sm text-text-primary">{r.title || 'Untitled'}</span>
              <span className="text-xs text-text-muted ml-4">{r.date_context}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className={`text-xs px-2 py-0.5 rounded ${
                r.status === 'published' ? 'bg-green-900 text-green-300' :
                r.status === 'pending' ? 'bg-yellow-900 text-yellow-300' :
                'bg-surface text-text-muted'
              }`}>
                {r.status}
              </span>
              {r.status === 'pending' && (
                <button
                  onClick={(e) => { e.stopPropagation(); handleStatusChange(r.id, 'published'); }}
                  className="text-xs px-2 py-0.5 bg-accent/20 text-accent rounded hover:bg-accent/30"
                >
                  Publish
                </button>
              )}
            </div>
          </div>
        ))}
        {readings.length === 0 && (
          <p className="text-text-muted text-sm">No readings yet.</p>
        )}
      </div>
    </div>
  );
}

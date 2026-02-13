import { useState, useEffect } from 'react';
import { apiGet } from '../api/client';

export default function EventsPage() {
  const [events, setEvents] = useState<any[]>([]);

  useEffect(() => {
    apiGet('/admin/events/').then(setEvents).catch(() => {});
  }, []);

  return (
    <div>
      <h1 className="text-xl mb-6 text-accent">Astronomical Events</h1>
      <div className="space-y-2">
        {events.map(e => (
          <div key={e.id} className="bg-surface-raised border border-text-ghost rounded p-3 flex justify-between">
            <div>
              <span className="text-sm text-text-primary">{e.event_type.replace(/_/g, ' ')}</span>
              {e.body && <span className="text-xs text-text-secondary ml-2">{e.body}</span>}
              {e.sign && <span className="text-xs text-text-muted ml-1">in {e.sign}</span>}
            </div>
            <div>
              <span className="text-xs text-text-muted">{new Date(e.at).toLocaleDateString()}</span>
              <span className={`text-xs ml-2 ${e.significance === 'major' ? 'text-accent' : 'text-text-muted'}`}>{e.significance}</span>
            </div>
          </div>
        ))}
        {events.length === 0 && <p className="text-text-muted text-sm">No events.</p>}
      </div>
    </div>
  );
}

import { useState, useEffect } from 'react';
import { apiGet, apiPut } from '../api/client';

export default function SettingsPage() {
  const [settings, setSettings] = useState<any[]>([]);

  useEffect(() => {
    apiGet('/admin/settings/').then(setSettings).catch(() => {});
  }, []);

  return (
    <div>
      <h1 className="text-xl mb-6 text-accent">Settings</h1>
      <div className="space-y-2">
        {settings.map(s => (
          <div key={s.key} className="bg-surface-raised border border-text-ghost rounded p-3 flex justify-between">
            <div>
              <span className="text-sm text-text-primary">{s.key}</span>
              <span className="text-xs text-text-muted ml-2">({s.category})</span>
            </div>
            <span className="text-xs text-text-secondary">{JSON.stringify(s.value)}</span>
          </div>
        ))}
        {settings.length === 0 && <p className="text-text-muted text-sm">No settings configured.</p>}
      </div>
    </div>
  );
}

import { useState, useEffect } from 'react';
import { apiGet } from '../api/client';

export default function DictionaryPage() {
  const [meanings, setMeanings] = useState<any[]>([]);

  useEffect(() => {
    apiGet('/admin/dictionary/').then(setMeanings).catch(() => {});
  }, []);

  return (
    <div>
      <h1 className="text-xl mb-6 text-accent">Archetypal Dictionary</h1>
      <div className="space-y-2">
        {meanings.map(m => (
          <div key={m.id} className="bg-surface-raised border border-text-ghost rounded p-3">
            <div className="text-sm text-accent">{m.body1}{m.body2 ? ` ${m.aspect_type || ''} ${m.body2}` : ''}</div>
            <div className="text-xs text-text-secondary mt-1">{m.core_meaning}</div>
            <div className="text-xs text-text-muted mt-1">{m.keywords?.join(', ')}</div>
          </div>
        ))}
        {meanings.length === 0 && <p className="text-text-muted text-sm">No dictionary entries.</p>}
      </div>
    </div>
  );
}

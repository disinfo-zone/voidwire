import { useState, useEffect } from 'react';
import { apiGet, apiPost, apiDelete } from '../api/client';

export default function SourcesPage() {
  const [sources, setSources] = useState<any[]>([]);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ name: '', url: '', domain: 'conflict', source_type: 'rss', weight: 0.5 });

  useEffect(() => {
    apiGet('/admin/sources/').then(setSources).catch(() => {});
  }, []);

  async function handleAdd() {
    await apiPost('/admin/sources/', form);
    setShowAdd(false);
    setSources(await apiGet('/admin/sources/'));
  }

  async function handleDelete(id: string) {
    await apiDelete(`/admin/sources/${id}`);
    setSources(sources.filter(s => s.id !== id));
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-xl text-accent">News Sources</h1>
        <button onClick={() => setShowAdd(!showAdd)} className="text-xs px-3 py-1 bg-surface-raised border border-text-ghost rounded text-accent hover:border-accent">
          + Add Source
        </button>
      </div>

      {showAdd && (
        <div className="bg-surface-raised border border-text-ghost rounded p-4 mb-4 space-y-2">
          <input placeholder="Name" value={form.name} onChange={e => setForm({...form, name: e.target.value})} className="w-full bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary" />
          <input placeholder="URL" value={form.url} onChange={e => setForm({...form, url: e.target.value})} className="w-full bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary" />
          <button onClick={handleAdd} className="text-xs px-3 py-1 bg-accent/20 text-accent rounded">Save</button>
        </div>
      )}

      <div className="space-y-2">
        {sources.map(s => (
          <div key={s.id} className="bg-surface-raised border border-text-ghost rounded p-3 flex justify-between items-center">
            <div>
              <span className="text-sm text-text-primary">{s.name}</span>
              <span className="text-xs text-text-muted ml-2">({s.source_type})</span>
              <span className={`ml-2 text-xs ${s.status === 'active' ? 'text-green-400' : 'text-text-muted'}`}>{s.status}</span>
            </div>
            <button onClick={() => handleDelete(s.id)} className="text-xs text-red-400 hover:text-red-300">delete</button>
          </div>
        ))}
      </div>
    </div>
  );
}

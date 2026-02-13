import { useState, useEffect, useRef } from 'react';
import { apiGet, apiPost, apiPatch, apiDelete } from '../api/client';

const EVENT_TYPES = ['aspect', 'retrograde', 'ingress', 'station', 'lunar_phase'];

export default function DictionaryPage() {
  const [meanings, setMeanings] = useState<any[]>([]);
  const [showAdd, setShowAdd] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [search, setSearch] = useState({ body1: '', event_type: '', q: '' });
  const [form, setForm] = useState({ body1: '', body2: '', aspect_type: '', event_type: 'aspect', core_meaning: '', keywords: '', domain_affinities: '', source: 'curated' });
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => { loadMeanings(); }, []);

  async function loadMeanings() {
    const params = new URLSearchParams();
    if (search.body1) params.set('body1', search.body1);
    if (search.event_type) params.set('event_type', search.event_type);
    if (search.q) params.set('q', search.q);
    const qs = params.toString();
    apiGet(`/admin/dictionary/${qs ? '?' + qs : ''}`).then(setMeanings).catch(() => {});
  }

  async function handleAdd() {
    await apiPost('/admin/dictionary/', {
      ...form,
      keywords: form.keywords.split(',').map((k) => k.trim()).filter(Boolean),
      domain_affinities: form.domain_affinities.split(',').map((k) => k.trim()).filter(Boolean),
    });
    setShowAdd(false);
    loadMeanings();
  }

  async function handleEdit(id: string) {
    await apiPatch(`/admin/dictionary/${id}`, {
      ...form,
      keywords: form.keywords.split(',').map((k) => k.trim()).filter(Boolean),
      domain_affinities: form.domain_affinities.split(',').map((k) => k.trim()).filter(Boolean),
    });
    setEditing(null);
    loadMeanings();
  }

  async function handleDelete(id: string) {
    await apiDelete(`/admin/dictionary/${id}`);
    setMeanings(meanings.filter((m) => m.id !== id));
  }

  async function handleBulkImport() {
    const file = fileInput.current?.files?.[0];
    if (!file) return;
    const text = await file.text();
    try {
      const entries = JSON.parse(text);
      await apiPost('/admin/dictionary/bulk-import', entries);
      loadMeanings();
    } catch (err) {
      console.error('Import failed:', err);
    }
  }

  function startEdit(m: any) {
    setEditing(m.id);
    setForm({
      body1: m.body1, body2: m.body2 || '', aspect_type: m.aspect_type || '',
      event_type: m.event_type, core_meaning: m.core_meaning,
      keywords: (m.keywords || []).join(', '),
      domain_affinities: (m.domain_affinities || []).join(', '),
      source: m.source,
    });
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-xl text-accent">Archetypal Dictionary</h1>
        <div className="flex gap-2">
          <input type="file" ref={fileInput} accept=".json" className="hidden" onChange={handleBulkImport} />
          <button onClick={() => fileInput.current?.click()} className="text-xs px-3 py-1 bg-surface-raised border border-text-ghost rounded text-text-muted hover:border-accent">
            Import JSON
          </button>
          <button onClick={() => setShowAdd(!showAdd)} className="text-xs px-3 py-1 bg-surface-raised border border-text-ghost rounded text-accent hover:border-accent">
            + Add Entry
          </button>
        </div>
      </div>

      {/* Search bar */}
      <div className="flex gap-2 mb-4">
        <input placeholder="Body1 (e.g. Mars)" value={search.body1} onChange={(e) => setSearch({ ...search, body1: e.target.value })} className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary" />
        <select value={search.event_type} onChange={(e) => setSearch({ ...search, event_type: e.target.value })} className="bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary">
          <option value="">All types</option>
          {EVENT_TYPES.map((t) => <option key={t}>{t}</option>)}
        </select>
        <input placeholder="Keyword search..." value={search.q} onChange={(e) => setSearch({ ...search, q: e.target.value })} className="flex-1 bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary" />
        <button onClick={loadMeanings} className="text-xs px-3 py-1 bg-accent/20 text-accent rounded">Search</button>
      </div>

      {showAdd && (
        <div className="bg-surface-raised border border-text-ghost rounded p-4 mb-4 space-y-2">
          <div className="grid grid-cols-4 gap-2">
            <input placeholder="Body1" value={form.body1} onChange={(e) => setForm({ ...form, body1: e.target.value })} className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary" />
            <input placeholder="Body2" value={form.body2} onChange={(e) => setForm({ ...form, body2: e.target.value })} className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary" />
            <input placeholder="Aspect type" value={form.aspect_type} onChange={(e) => setForm({ ...form, aspect_type: e.target.value })} className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary" />
            <select value={form.event_type} onChange={(e) => setForm({ ...form, event_type: e.target.value })} className="bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary">
              {EVENT_TYPES.map((t) => <option key={t}>{t}</option>)}
            </select>
          </div>
          <textarea placeholder="Core meaning" value={form.core_meaning} onChange={(e) => setForm({ ...form, core_meaning: e.target.value })} rows={2} className="w-full bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary" />
          <div className="grid grid-cols-2 gap-2">
            <input placeholder="Keywords (comma-separated)" value={form.keywords} onChange={(e) => setForm({ ...form, keywords: e.target.value })} className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary" />
            <input placeholder="Domain affinities (comma-separated)" value={form.domain_affinities} onChange={(e) => setForm({ ...form, domain_affinities: e.target.value })} className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary" />
          </div>
          <button onClick={handleAdd} className="text-xs px-3 py-1 bg-accent/20 text-accent rounded">Save</button>
        </div>
      )}

      <div className="space-y-2">
        {meanings.map((m) => (
          <div key={m.id} className="bg-surface-raised border border-text-ghost rounded p-3">
            {editing === m.id ? (
              <div className="space-y-2">
                <div className="grid grid-cols-4 gap-2">
                  <input value={form.body1} onChange={(e) => setForm({ ...form, body1: e.target.value })} className="bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary" />
                  <input value={form.body2} onChange={(e) => setForm({ ...form, body2: e.target.value })} className="bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary" />
                  <input value={form.aspect_type} onChange={(e) => setForm({ ...form, aspect_type: e.target.value })} className="bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary" />
                  <select value={form.event_type} onChange={(e) => setForm({ ...form, event_type: e.target.value })} className="bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary">
                    {EVENT_TYPES.map((t) => <option key={t}>{t}</option>)}
                  </select>
                </div>
                <textarea value={form.core_meaning} onChange={(e) => setForm({ ...form, core_meaning: e.target.value })} rows={2} className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary" />
                <input value={form.keywords} onChange={(e) => setForm({ ...form, keywords: e.target.value })} className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary" />
                <div className="flex gap-2">
                  <button onClick={() => handleEdit(m.id)} className="text-xs px-2 py-1 bg-accent/20 text-accent rounded">Save</button>
                  <button onClick={() => setEditing(null)} className="text-xs px-2 py-1 text-text-muted">Cancel</button>
                </div>
              </div>
            ) : (
              <div className="flex justify-between">
                <div>
                  <div className="text-sm text-accent">{m.body1}{m.body2 ? ` ${m.aspect_type || ''} ${m.body2}` : ''} <span className="text-text-muted text-xs">({m.event_type})</span></div>
                  <div className="text-xs text-text-secondary mt-1">{m.core_meaning}</div>
                  {m.keywords?.length > 0 && <div className="text-xs text-text-muted mt-1">{m.keywords.join(', ')}</div>}
                </div>
                <div className="flex gap-2 shrink-0">
                  <button onClick={() => startEdit(m)} className="text-xs text-text-muted hover:text-accent">edit</button>
                  <button onClick={() => handleDelete(m.id)} className="text-xs text-red-400 hover:text-red-300">delete</button>
                </div>
              </div>
            )}
          </div>
        ))}
        {meanings.length === 0 && <p className="text-text-muted text-sm">No dictionary entries.</p>}
      </div>
    </div>
  );
}

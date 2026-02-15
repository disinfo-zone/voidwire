import { useState, useEffect, useRef } from 'react';
import { apiGet, apiPost, apiPatch, apiPut, apiDelete } from '../api/client';
import { useToast } from '../components/ui/ToastProvider';
import ConfirmDialog from '../components/ui/ConfirmDialog';
import Spinner from '../components/ui/Spinner';

const EVENT_TYPES = ['aspect', 'retrograde', 'ingress', 'station', 'lunar_phase'];

type Tab = 'meanings' | 'planetary' | 'aspect';

const GUIDE_BY_TAB: Record<
  Tab,
  {
    label: string;
    useWhen: string;
    requiredFields: string;
    workflow: string[];
  }
> = {
  meanings: {
    label: 'Archetypal Meanings',
    useWhen: 'Use this tab for event-level interpretations (specific body/body pair + event type). These are the most specific overrides.',
    requiredFields: 'Set body1 and event_type. Use body2 + aspect_type for pair/aspect entries. Add keywords/domain affinities as comma-separated lists.',
    workflow: [
      'Search before adding to avoid duplicate entries for the same body/event combination.',
      'Write a concise core meaning in plain language; keep it reusable across dates.',
      'Add 5-12 keywords that should influence synthesis and selection.',
      'Use domain affinities (politics, culture, economy, etc.) to steer thematic weighting.',
    ],
  },
  planetary: {
    label: 'Planetary Keywords',
    useWhen: 'Use this tab for baseline descriptors per single body (Sun, Moon, Mars, etc.) regardless of event type.',
    requiredFields: 'Set body and keywords. Archetype is optional but recommended. Domain affinities are comma-separated.',
    workflow: [
      'Define broad, stable planetary traits only; avoid event-specific language here.',
      'Keep keyword lists tight and non-redundant to reduce prompt noise.',
      'Use archetype as a short mnemonic label (e.g. initiator, nurturer, disruptor).',
      'Prefer edits over adding near-duplicates with alternate body names.',
    ],
  },
  aspect: {
    label: 'Aspect Keywords',
    useWhen: 'Use this tab for baseline descriptors by aspect type (conjunction, square, trine, etc.).',
    requiredFields: 'Set aspect_type and keywords. Archetype is optional and should stay high level.',
    workflow: [
      'Describe the aspect dynamic itself, not specific planets.',
      'Use keywords that can apply across many pairings to keep this layer generic.',
      'If an interpretation should apply only to one pairing, put it in Archetypal Meanings instead.',
      'After major edits, run a manual pipeline trigger and review the resulting reading language.',
    ],
  },
};

function DictionaryGuide({ activeTab }: { activeTab: Tab }) {
  const guide = GUIDE_BY_TAB[activeTab];

  return (
    <div className="bg-surface-raised border border-text-ghost rounded p-4 mb-6">
      <div className="text-[11px] uppercase tracking-wider text-text-muted mb-2">Help & Guide</div>
      <div className="text-sm text-text-secondary mb-2">
        Dictionary entries steer interpretation quality. Use the most specific tab possible so the model gets clear, non-conflicting signals.
      </div>
      <div className="text-sm text-accent mb-1">Current tab: {guide.label}</div>
      <div className="text-xs text-text-muted mb-1">
        <span className="text-text-secondary">When to use:</span> {guide.useWhen}
      </div>
      <div className="text-xs text-text-muted mb-3">
        <span className="text-text-secondary">Field expectations:</span> {guide.requiredFields}
      </div>
      <ol className="list-decimal list-inside text-xs text-text-muted space-y-1">
        {guide.workflow.map((step) => (
          <li key={step}>{step}</li>
        ))}
      </ol>
    </div>
  );
}

export default function DictionaryPage() {
  const [activeTab, setActiveTab] = useState<Tab>('meanings');

  return (
    <div>
      <h1 className="text-xl mb-6 text-accent">Archetypal Dictionary</h1>
      <DictionaryGuide activeTab={activeTab} />

      <div className="flex gap-1 mb-6 border-b border-text-ghost overflow-x-auto">
        {([['meanings', 'Archetypal Meanings'], ['planetary', 'Planetary Keywords'], ['aspect', 'Aspect Keywords']] as [Tab, string][]).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`px-4 py-2 text-sm border-b-2 -mb-px transition-colors whitespace-nowrap ${
              activeTab === key ? 'border-accent text-accent' : 'border-transparent text-text-muted hover:text-text-primary'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {activeTab === 'meanings' && <MeaningsTab />}
      {activeTab === 'planetary' && <PlanetaryTab />}
      {activeTab === 'aspect' && <AspectTab />}
    </div>
  );
}

function MeaningsTab() {
  const [meanings, setMeanings] = useState<any[]>([]);
  const [showAdd, setShowAdd] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [search, setSearch] = useState({ body1: '', event_type: '', q: '' });
  const [form, setForm] = useState({ body1: '', body2: '', aspect_type: '', event_type: 'aspect', core_meaning: '', keywords: '', domain_affinities: '', source: 'curated' });
  const [loading, setLoading] = useState(true);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const { toast } = useToast();

  useEffect(() => { loadMeanings(); }, []);

  async function loadMeanings() {
    setLoading(true);
    const params = new URLSearchParams();
    if (search.body1) params.set('body1', search.body1);
    if (search.event_type) params.set('event_type', search.event_type);
    if (search.q) params.set('q', search.q);
    const qs = params.toString();
    try {
      const data = await apiGet(`/admin/dictionary/${qs ? '?' + qs : ''}`);
      setMeanings(data);
    } catch (e: any) {
      toast.error(e.message);
    }
    setLoading(false);
  }

  async function handleAdd() {
    try {
      await apiPost('/admin/dictionary/', {
        ...form,
        keywords: form.keywords.split(',').map((k) => k.trim()).filter(Boolean),
        domain_affinities: form.domain_affinities.split(',').map((k) => k.trim()).filter(Boolean),
      });
      setShowAdd(false);
      loadMeanings();
      toast.success('Entry added');
    } catch (e: any) {
      toast.error(e.message);
    }
  }

  async function handleEdit(id: string) {
    try {
      await apiPatch(`/admin/dictionary/${id}`, {
        ...form,
        keywords: form.keywords.split(',').map((k) => k.trim()).filter(Boolean),
        domain_affinities: form.domain_affinities.split(',').map((k) => k.trim()).filter(Boolean),
      });
      setEditing(null);
      loadMeanings();
      toast.success('Entry updated');
    } catch (e: any) {
      toast.error(e.message);
    }
  }

  async function confirmDelete() {
    if (!deleteId) return;
    try {
      await apiDelete(`/admin/dictionary/${deleteId}`);
      setMeanings(meanings.filter((m) => m.id !== deleteId));
      toast.success('Entry deleted');
    } catch (e: any) {
      toast.error(e.message);
    }
    setDeleteId(null);
  }

  async function handleBulkImport() {
    const file = fileInput.current?.files?.[0];
    if (!file) return;
    const text = await file.text();
    try {
      const entries = JSON.parse(text);
      await apiPost('/admin/dictionary/bulk-import', entries);
      toast.success('Import successful');
      loadMeanings();
    } catch (e: any) {
      toast.error(e.message || 'Import failed');
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
      <div className="flex justify-between items-center mb-4">
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

      <div className="flex gap-2 mb-4 flex-wrap">
        <input placeholder="Body1 (e.g. Mars)" value={search.body1} onChange={(e) => setSearch({ ...search, body1: e.target.value })} className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary" />
        <select value={search.event_type} onChange={(e) => setSearch({ ...search, event_type: e.target.value })} className="bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary">
          <option value="">All types</option>
          {EVENT_TYPES.map((t) => <option key={t}>{t}</option>)}
        </select>
        <input placeholder="Keyword search..." value={search.q} onChange={(e) => setSearch({ ...search, q: e.target.value })} className="flex-1 min-w-[120px] bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary" />
        <button onClick={loadMeanings} className="text-xs px-3 py-1 bg-accent/20 text-accent rounded">Search</button>
      </div>

      {showAdd && (
        <div className="bg-surface-raised border border-text-ghost rounded p-4 mb-4 space-y-2">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <input placeholder="Body1" value={form.body1} onChange={(e) => setForm({ ...form, body1: e.target.value })} className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary" />
            <input placeholder="Body2" value={form.body2} onChange={(e) => setForm({ ...form, body2: e.target.value })} className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary" />
            <input placeholder="Aspect type" value={form.aspect_type} onChange={(e) => setForm({ ...form, aspect_type: e.target.value })} className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary" />
            <select value={form.event_type} onChange={(e) => setForm({ ...form, event_type: e.target.value })} className="bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary">
              {EVENT_TYPES.map((t) => <option key={t}>{t}</option>)}
            </select>
          </div>
          <textarea placeholder="Core meaning" value={form.core_meaning} onChange={(e) => setForm({ ...form, core_meaning: e.target.value })} rows={2} className="w-full bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary" />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <input placeholder="Keywords (comma-separated)" value={form.keywords} onChange={(e) => setForm({ ...form, keywords: e.target.value })} className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary" />
            <input placeholder="Domain affinities (comma-separated)" value={form.domain_affinities} onChange={(e) => setForm({ ...form, domain_affinities: e.target.value })} className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary" />
          </div>
          <button onClick={handleAdd} className="text-xs px-3 py-1 bg-accent/20 text-accent rounded">Save</button>
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-12"><Spinner /></div>
      ) : (
        <div className="space-y-2">
          {meanings.map((m) => (
            <div key={m.id} className="bg-surface-raised border border-text-ghost rounded p-3">
              {editing === m.id ? (
                <div className="space-y-2">
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
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
                    <button onClick={() => setDeleteId(m.id)} className="text-xs text-red-400 hover:text-red-300">delete</button>
                  </div>
                </div>
              )}
            </div>
          ))}
          {meanings.length === 0 && <p className="text-text-muted text-sm">No dictionary entries.</p>}
        </div>
      )}

      <ConfirmDialog
        open={!!deleteId}
        title="Delete Entry"
        message="Are you sure you want to delete this dictionary entry?"
        onConfirm={confirmDelete}
        onCancel={() => setDeleteId(null)}
        destructive
      />
    </div>
  );
}

function PlanetaryTab() {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<string | null>(null);
  const [form, setForm] = useState({ body: '', keywords: '', archetype: '', domain_affinities: '' });
  const [showAdd, setShowAdd] = useState(false);
  const [deleteBody, setDeleteBody] = useState<string | null>(null);
  const { toast } = useToast();

  useEffect(() => { load(); }, []);

  async function load() {
    setLoading(true);
    try {
      const data = await apiGet('/admin/keywords/planetary');
      setItems(data);
    } catch (e: any) {
      toast.error(e.message);
    }
    setLoading(false);
  }

  async function handleSave(body: string) {
    try {
      await apiPut(`/admin/keywords/planetary/${encodeURIComponent(body)}`, {
        keywords: form.keywords.split(',').map((k) => k.trim()).filter(Boolean),
        archetype: form.archetype,
        domain_affinities: form.domain_affinities.split(',').map((k) => k.trim()).filter(Boolean),
      });
      setEditing(null);
      setShowAdd(false);
      load();
      toast.success('Saved');
    } catch (e: any) {
      toast.error(e.message);
    }
  }

  async function confirmDelete() {
    if (!deleteBody) return;
    try {
      await apiDelete(`/admin/keywords/planetary/${encodeURIComponent(deleteBody)}`);
      setItems(items.filter((i) => i.body !== deleteBody));
      toast.success('Deleted');
    } catch (e: any) {
      toast.error(e.message);
    }
    setDeleteBody(null);
  }

  function startEdit(item: any) {
    setEditing(item.body);
    setForm({
      body: item.body,
      keywords: (item.keywords || []).join(', '),
      archetype: item.archetype || '',
      domain_affinities: (item.domain_affinities || []).join(', '),
    });
  }

  if (loading) return <div className="flex justify-center py-12"><Spinner /></div>;

  return (
    <div>
      <div className="flex justify-end mb-4">
        <button onClick={() => { setShowAdd(true); setForm({ body: '', keywords: '', archetype: '', domain_affinities: '' }); }} className="text-xs px-3 py-1 bg-surface-raised border border-text-ghost rounded text-accent hover:border-accent">+ Add</button>
      </div>

      {showAdd && (
        <div className="bg-surface-raised border border-text-ghost rounded p-4 mb-4 space-y-2">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <input placeholder="Body (e.g. Sun)" value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary" />
            <input placeholder="Archetype" value={form.archetype} onChange={(e) => setForm({ ...form, archetype: e.target.value })} className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary" />
          </div>
          <input placeholder="Keywords (comma-separated)" value={form.keywords} onChange={(e) => setForm({ ...form, keywords: e.target.value })} className="w-full bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary" />
          <input placeholder="Domain affinities (comma-separated)" value={form.domain_affinities} onChange={(e) => setForm({ ...form, domain_affinities: e.target.value })} className="w-full bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary" />
          <div className="flex gap-2">
            <button onClick={() => handleSave(form.body)} className="text-xs px-3 py-1 bg-accent/20 text-accent rounded">Save</button>
            <button onClick={() => setShowAdd(false)} className="text-xs px-2 py-1 text-text-muted">Cancel</button>
          </div>
        </div>
      )}

      <div className="space-y-2">
        {items.map((item) => (
          <div key={item.body} className="bg-surface-raised border border-text-ghost rounded p-3">
            {editing === item.body ? (
              <div className="space-y-2">
                <input placeholder="Archetype" value={form.archetype} onChange={(e) => setForm({ ...form, archetype: e.target.value })} className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary" />
                <input placeholder="Keywords" value={form.keywords} onChange={(e) => setForm({ ...form, keywords: e.target.value })} className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary" />
                <input placeholder="Domain affinities" value={form.domain_affinities} onChange={(e) => setForm({ ...form, domain_affinities: e.target.value })} className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary" />
                <div className="flex gap-2">
                  <button onClick={() => handleSave(item.body)} className="text-xs px-2 py-1 bg-accent/20 text-accent rounded">Save</button>
                  <button onClick={() => setEditing(null)} className="text-xs px-2 py-1 text-text-muted">Cancel</button>
                </div>
              </div>
            ) : (
              <div className="flex justify-between">
                <div>
                  <div className="text-sm text-accent">{item.body} <span className="text-text-muted text-xs">({item.archetype})</span></div>
                  <div className="text-xs text-text-secondary mt-1">{(item.keywords || []).join(', ')}</div>
                  {item.domain_affinities?.length > 0 && <div className="text-xs text-text-muted mt-1">Domains: {item.domain_affinities.join(', ')}</div>}
                </div>
                <div className="flex gap-2 shrink-0">
                  <button onClick={() => startEdit(item)} className="text-xs text-text-muted hover:text-accent">edit</button>
                  <button onClick={() => setDeleteBody(item.body)} className="text-xs text-red-400 hover:text-red-300">delete</button>
                </div>
              </div>
            )}
          </div>
        ))}
        {items.length === 0 && <p className="text-text-muted text-sm">No planetary keywords.</p>}
      </div>

      <ConfirmDialog open={!!deleteBody} title="Delete Planetary Keyword" message={`Delete keywords for "${deleteBody}"?`} onConfirm={confirmDelete} onCancel={() => setDeleteBody(null)} destructive />
    </div>
  );
}

function AspectTab() {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<string | null>(null);
  const [form, setForm] = useState({ aspect_type: '', keywords: '', archetype: '' });
  const [showAdd, setShowAdd] = useState(false);
  const [deleteType, setDeleteType] = useState<string | null>(null);
  const { toast } = useToast();

  useEffect(() => { load(); }, []);

  async function load() {
    setLoading(true);
    try {
      const data = await apiGet('/admin/keywords/aspect');
      setItems(data);
    } catch (e: any) {
      toast.error(e.message);
    }
    setLoading(false);
  }

  async function handleSave(aspectType: string) {
    try {
      await apiPut(`/admin/keywords/aspect/${encodeURIComponent(aspectType)}`, {
        keywords: form.keywords.split(',').map((k) => k.trim()).filter(Boolean),
        archetype: form.archetype,
      });
      setEditing(null);
      setShowAdd(false);
      load();
      toast.success('Saved');
    } catch (e: any) {
      toast.error(e.message);
    }
  }

  async function confirmDelete() {
    if (!deleteType) return;
    try {
      await apiDelete(`/admin/keywords/aspect/${encodeURIComponent(deleteType)}`);
      setItems(items.filter((i) => i.aspect_type !== deleteType));
      toast.success('Deleted');
    } catch (e: any) {
      toast.error(e.message);
    }
    setDeleteType(null);
  }

  function startEdit(item: any) {
    setEditing(item.aspect_type);
    setForm({
      aspect_type: item.aspect_type,
      keywords: (item.keywords || []).join(', '),
      archetype: item.archetype || '',
    });
  }

  if (loading) return <div className="flex justify-center py-12"><Spinner /></div>;

  return (
    <div>
      <div className="flex justify-end mb-4">
        <button onClick={() => { setShowAdd(true); setForm({ aspect_type: '', keywords: '', archetype: '' }); }} className="text-xs px-3 py-1 bg-surface-raised border border-text-ghost rounded text-accent hover:border-accent">+ Add</button>
      </div>

      {showAdd && (
        <div className="bg-surface-raised border border-text-ghost rounded p-4 mb-4 space-y-2">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <input placeholder="Aspect type (e.g. conjunction)" value={form.aspect_type} onChange={(e) => setForm({ ...form, aspect_type: e.target.value })} className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary" />
            <input placeholder="Archetype" value={form.archetype} onChange={(e) => setForm({ ...form, archetype: e.target.value })} className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary" />
          </div>
          <input placeholder="Keywords (comma-separated)" value={form.keywords} onChange={(e) => setForm({ ...form, keywords: e.target.value })} className="w-full bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary" />
          <div className="flex gap-2">
            <button onClick={() => handleSave(form.aspect_type)} className="text-xs px-3 py-1 bg-accent/20 text-accent rounded">Save</button>
            <button onClick={() => setShowAdd(false)} className="text-xs px-2 py-1 text-text-muted">Cancel</button>
          </div>
        </div>
      )}

      <div className="space-y-2">
        {items.map((item) => (
          <div key={item.aspect_type} className="bg-surface-raised border border-text-ghost rounded p-3">
            {editing === item.aspect_type ? (
              <div className="space-y-2">
                <input placeholder="Archetype" value={form.archetype} onChange={(e) => setForm({ ...form, archetype: e.target.value })} className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary" />
                <input placeholder="Keywords" value={form.keywords} onChange={(e) => setForm({ ...form, keywords: e.target.value })} className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary" />
                <div className="flex gap-2">
                  <button onClick={() => handleSave(item.aspect_type)} className="text-xs px-2 py-1 bg-accent/20 text-accent rounded">Save</button>
                  <button onClick={() => setEditing(null)} className="text-xs px-2 py-1 text-text-muted">Cancel</button>
                </div>
              </div>
            ) : (
              <div className="flex justify-between">
                <div>
                  <div className="text-sm text-accent">{item.aspect_type} <span className="text-text-muted text-xs">({item.archetype})</span></div>
                  <div className="text-xs text-text-secondary mt-1">{(item.keywords || []).join(', ')}</div>
                </div>
                <div className="flex gap-2 shrink-0">
                  <button onClick={() => startEdit(item)} className="text-xs text-text-muted hover:text-accent">edit</button>
                  <button onClick={() => setDeleteType(item.aspect_type)} className="text-xs text-red-400 hover:text-red-300">delete</button>
                </div>
              </div>
            )}
          </div>
        ))}
        {items.length === 0 && <p className="text-text-muted text-sm">No aspect keywords.</p>}
      </div>

      <ConfirmDialog open={!!deleteType} title="Delete Aspect Keyword" message={`Delete keywords for "${deleteType}"?`} onConfirm={confirmDelete} onCancel={() => setDeleteType(null)} destructive />
    </div>
  );
}

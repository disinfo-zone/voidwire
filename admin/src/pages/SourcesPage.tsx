import { useState, useEffect } from 'react';
import { apiGet, apiPost, apiPatch, apiDelete } from '../api/client';
import { useToast } from '../components/ui/ToastProvider';
import ConfirmDialog from '../components/ui/ConfirmDialog';
import Spinner from '../components/ui/Spinner';

const DOMAINS = ['conflict', 'diplomacy', 'economy', 'technology', 'culture', 'environment', 'social', 'anomalous', 'legal', 'health'];

type StarterSource = {
  name: string;
  url: string;
  domain: string;
  note?: string;
};

const STARTER_SOURCES: StarterSource[] = [
  { name: 'BBC World', url: 'https://feeds.bbci.co.uk/news/world/rss.xml', domain: 'diplomacy' },
  { name: 'UN News (All)', url: 'https://news.un.org/feed/subscribe/en/news/all/rss.xml', domain: 'diplomacy' },
  { name: 'BBC Business', url: 'https://feeds.bbci.co.uk/news/business/rss.xml', domain: 'economy' },
  { name: 'TechCrunch', url: 'https://techcrunch.com/feed/', domain: 'technology' },
  { name: 'The Verge', url: 'https://www.theverge.com/rss/index.xml', domain: 'technology' },
  { name: 'Guardian Culture (US)', url: 'https://www.theguardian.com/us/culture/rss', domain: 'culture' },
  { name: 'Guardian Environment (US)', url: 'https://www.theguardian.com/us/environment/rss', domain: 'environment' },
  { name: 'WHO News', url: 'https://www.who.int/rss-feeds/news-english.xml', domain: 'health' },
  { name: 'SCOTUSblog', url: 'https://www.scotusblog.com/feed/', domain: 'legal' },
  { name: 'NASA News Releases', url: 'https://www.nasa.gov/news-release/feed/', domain: 'anomalous' },
];

export default function SourcesPage() {
  const [sources, setSources] = useState<any[]>([]);
  const [showAdd, setShowAdd] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [form, setForm] = useState({ name: '', url: '', domain: 'conflict', source_type: 'rss', weight: 0.5, max_articles: 10, allow_fulltext: false, config: '{}' });
  const [testResult, setTestResult] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const { toast } = useToast();

  useEffect(() => { loadSources(); }, []);

  function useStarterSource(starter: StarterSource) {
    setShowAdd(true);
    setForm({
      name: starter.name,
      url: starter.url,
      domain: starter.domain,
      source_type: 'rss',
      weight: 0.6,
      max_articles: 10,
      allow_fulltext: false,
      config: '{}',
    });
  }

  async function loadSources() {
    setLoading(true);
    try {
      const data = await apiGet('/admin/sources/');
      setSources(data);
    } catch (e: any) {
      toast.error(e.message);
    }
    setLoading(false);
  }

  async function handleAdd() {
    let cfg = {};
    try { cfg = JSON.parse(form.config); } catch {}
    try {
      await apiPost('/admin/sources/', { ...form, config: cfg });
      setShowAdd(false);
      setForm({ name: '', url: '', domain: 'conflict', source_type: 'rss', weight: 0.5, max_articles: 10, allow_fulltext: false, config: '{}' });
      loadSources();
      toast.success('Source added');
    } catch (e: any) {
      toast.error(e.message);
    }
  }

  async function handleEdit(id: string) {
    let cfg = {};
    try { cfg = JSON.parse(form.config); } catch {}
    try {
      await apiPatch(`/admin/sources/${id}`, { name: form.name, url: form.url, domain: form.domain, weight: form.weight, max_articles: form.max_articles, allow_fulltext: form.allow_fulltext, config: cfg });
      setEditing(null);
      loadSources();
      toast.success('Source updated');
    } catch (e: any) {
      toast.error(e.message);
    }
  }

  async function confirmDelete() {
    if (!deleteId) return;
    try {
      await apiDelete(`/admin/sources/${deleteId}`);
      setSources(sources.filter((s) => s.id !== deleteId));
      toast.success('Source deleted');
    } catch (e: any) {
      toast.error(e.message);
    }
    setDeleteId(null);
  }

  async function handleTest(id: string) {
    try {
      const result = await apiPost(`/admin/sources/${id}/test-fetch`, {});
      setTestResult((prev) => ({ ...prev, [id]: result }));
    } catch (err) {
      setTestResult((prev) => ({ ...prev, [id]: { status: 'error', error: String(err) } }));
    }
  }

  function startEdit(s: any) {
    setEditing(s.id);
    setForm({ name: s.name, url: s.url, domain: s.domain, source_type: s.source_type, weight: s.weight, max_articles: s.max_articles || 10, allow_fulltext: s.allow_fulltext || false, config: JSON.stringify(s.config || {}, null, 2) });
  }

  if (loading) return <div><h1 className="text-xl mb-6 text-accent">News Sources</h1><div className="flex justify-center py-12"><Spinner /></div></div>;

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-xl text-accent">News Sources</h1>
        <button onClick={() => setShowAdd(!showAdd)} className="text-xs px-3 py-1 bg-surface-raised border border-text-ghost rounded text-accent hover:border-accent">
          + Add Source
        </button>
      </div>

      <div className="bg-surface-raised border border-text-ghost rounded p-4 mb-4 space-y-3">
        <h2 className="text-sm text-text-primary">Quick Guide</h2>
        <p className="text-xs text-text-muted">
          Start with RSS feeds and keep <span className="font-mono">Config JSON</span> as <span className="font-mono">{'{}'}</span>.
          The domain dropdown is a broad tag used for balancing, not a strict classifier.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-xs">
          <div className="bg-surface border border-text-ghost rounded px-3 py-2">
            <div className="text-text-secondary mb-1">URL</div>
            <div className="text-text-muted">Use a direct feed URL ending in <span className="font-mono">.xml</span> or <span className="font-mono">/rss</span>.</div>
          </div>
          <div className="bg-surface border border-text-ghost rounded px-3 py-2">
            <div className="text-text-secondary mb-1">Weight</div>
            <div className="text-text-muted">Use <span className="font-mono">0.4</span> to <span className="font-mono">0.7</span> for most sources.</div>
          </div>
          <div className="bg-surface border border-text-ghost rounded px-3 py-2">
            <div className="text-text-secondary mb-1">Max Articles</div>
            <div className="text-text-muted">Use <span className="font-mono">5-15</span> while testing to keep runs fast.</div>
          </div>
        </div>
        <div>
          <h3 className="text-xs uppercase tracking-wider text-text-secondary mb-2">Starter Feeds (Tested)</h3>
          <div className="space-y-2">
            {STARTER_SOURCES.map((s) => (
              <div key={s.url} className="bg-surface border border-text-ghost rounded px-3 py-2 flex flex-col md:flex-row md:items-center md:justify-between gap-2">
                <div className="min-w-0">
                  <div className="text-sm text-text-primary flex items-center gap-2 flex-wrap">
                    <span>{s.name}</span>
                    <span className="text-[11px] px-2 py-0.5 rounded bg-surface-raised border border-text-ghost text-text-muted">{s.domain}</span>
                  </div>
                  <div className="text-xs text-text-muted break-all">{s.url}</div>
                  {s.note && <div className="text-xs text-text-ghost mt-1">{s.note}</div>}
                </div>
                <button
                  onClick={() => useStarterSource(s)}
                  className="text-xs px-3 py-1 bg-accent/20 text-accent rounded hover:bg-accent/30 shrink-0"
                >
                  Use Preset
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>

      {showAdd && (
        <div className="bg-surface-raised border border-text-ghost rounded p-4 mb-4 space-y-2">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <input placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary" />
            <input placeholder="URL" value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary" />
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <select value={form.domain} onChange={(e) => setForm({ ...form, domain: e.target.value })} className="bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary">
              {DOMAINS.map((d) => <option key={d}>{d}</option>)}
            </select>
            <div className="flex items-center gap-2">
              <label className="text-xs text-text-muted">Weight</label>
              <input type="range" min="0" max="1" step="0.05" value={form.weight} onChange={(e) => setForm({ ...form, weight: parseFloat(e.target.value) })} className="flex-1 accent-accent" />
              <span className="text-xs text-text-primary w-8">{form.weight}</span>
            </div>
            <div className="flex items-center gap-2">
              <label className="text-xs text-text-muted">Max</label>
              <input type="number" value={form.max_articles} onChange={(e) => setForm({ ...form, max_articles: parseInt(e.target.value) || 10 })} className="w-16 bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary" />
            </div>
            <label className="flex items-center gap-2 text-xs text-text-muted">
              <input type="checkbox" checked={form.allow_fulltext} onChange={(e) => setForm({ ...form, allow_fulltext: e.target.checked })} />
              Fulltext
            </label>
          </div>
          <textarea placeholder="Config JSON" value={form.config} onChange={(e) => setForm({ ...form, config: e.target.value })} rows={2} className="w-full bg-surface border border-text-ghost rounded px-3 py-1 text-xs text-text-primary font-mono" />
          <button onClick={handleAdd} className="text-xs px-3 py-1 bg-accent/20 text-accent rounded">Save</button>
        </div>
      )}

      <div className="space-y-2">
        {sources.map((s) => (
          <div key={s.id} className="bg-surface-raised border border-text-ghost rounded p-4">
            {editing === s.id ? (
              <div className="space-y-2">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary" />
                  <input value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary" />
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  <select value={form.domain} onChange={(e) => setForm({ ...form, domain: e.target.value })} className="bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary">
                    {DOMAINS.map((d) => <option key={d}>{d}</option>)}
                  </select>
                  <input type="range" min="0" max="1" step="0.05" value={form.weight} onChange={(e) => setForm({ ...form, weight: parseFloat(e.target.value) })} className="accent-accent" />
                  <input type="number" value={form.max_articles} onChange={(e) => setForm({ ...form, max_articles: parseInt(e.target.value) || 10 })} className="w-16 bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary" />
                  <label className="flex items-center gap-1 text-xs text-text-muted"><input type="checkbox" checked={form.allow_fulltext} onChange={(e) => setForm({ ...form, allow_fulltext: e.target.checked })} /> Fulltext</label>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => handleEdit(s.id)} className="text-xs px-2 py-1 bg-accent/20 text-accent rounded">Save</button>
                  <button onClick={() => setEditing(null)} className="text-xs px-2 py-1 text-text-muted">Cancel</button>
                </div>
              </div>
            ) : (
              <div className="flex flex-col sm:flex-row justify-between items-start gap-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm text-text-primary">{s.name}</span>
                    <span className="text-xs text-text-muted">({s.source_type})</span>
                    <span className={`text-xs ${s.status === 'active' ? 'text-green-400' : 'text-text-muted'}`}>{s.status}</span>
                    <span className="text-xs text-text-muted">w={s.weight}</span>
                    <span className="text-xs text-text-muted">{s.domain}</span>
                  </div>
                  <div className="text-xs text-text-muted mt-1 truncate">{s.url}</div>
                  {s.last_error && <div className="text-xs text-red-400 mt-1">{s.last_error}</div>}
                  {s.last_fetch_at && <div className="text-xs text-text-muted mt-1">Last fetch: {new Date(s.last_fetch_at).toLocaleDateString()}</div>}
                </div>
                <div className="flex gap-2 shrink-0">
                  <button onClick={() => handleTest(s.id)} className="text-xs text-text-muted hover:text-accent">test</button>
                  <button onClick={() => startEdit(s)} className="text-xs text-text-muted hover:text-accent">edit</button>
                  <button onClick={() => setDeleteId(s.id)} className="text-xs text-red-400 hover:text-red-300">delete</button>
                </div>
              </div>
            )}
            {testResult[s.id] && (
              <div className={`mt-2 text-xs p-2 rounded ${testResult[s.id].status === 'ok' ? 'bg-green-900/30 text-green-300' : 'bg-red-900/30 text-red-300'}`}>
                {testResult[s.id].status === 'ok'
                  ? `Fetched ${testResult[s.id].count} articles`
                  : `Error: ${testResult[s.id].error}`
                }
              </div>
            )}
          </div>
        ))}
      </div>

      <ConfirmDialog
        open={!!deleteId}
        title="Delete Source"
        message="Are you sure you want to delete this source?"
        onConfirm={confirmDelete}
        onCancel={() => setDeleteId(null)}
        destructive
      />
    </div>
  );
}

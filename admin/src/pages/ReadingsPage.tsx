import { useState, useEffect } from 'react';
import { apiGet, apiPatch, apiPost } from '../api/client';
import ReadingEditor from '../components/readings/ReadingEditor';
import DiffViewer from '../components/readings/DiffViewer';

const STATUSES = ['', 'pending', 'approved', 'rejected', 'published', 'archived'];

export default function ReadingsPage() {
  const [readings, setReadings] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);
  const [detail, setDetail] = useState<any>(null);
  const [signals, setSignals] = useState<any[]>([]);
  const [diff, setDiff] = useState<any>(null);
  const [filter, setFilter] = useState('');
  const [view, setView] = useState<'detail' | 'edit' | 'diff' | 'signals'>('detail');
  const [regenMode, setRegenMode] = useState('prose_only');

  useEffect(() => {
    loadReadings();
  }, [filter]);

  async function loadReadings() {
    const params = filter ? `?status=${filter}` : '';
    apiGet(`/admin/readings/${params}`).then(setReadings).catch(() => {});
  }

  async function selectReading(r: any) {
    setSelected(r);
    setView('detail');
    try {
      const d = await apiGet(`/admin/readings/${r.id}`);
      setDetail(d);
    } catch {}
  }

  async function handleStatusChange(status: string) {
    if (!selected) return;
    await apiPatch(`/admin/readings/${selected.id}`, { status });
    setReadings(readings.map((r) => r.id === selected.id ? { ...r, status } : r));
    if (detail) setDetail({ ...detail, status });
  }

  async function handleSaveContent(data: any) {
    if (!selected) return;
    await apiPatch(`/admin/readings/${selected.id}/content`, data);
    const d = await apiGet(`/admin/readings/${selected.id}`);
    setDetail(d);
  }

  async function loadDiff() {
    if (!selected) return;
    const d = await apiGet(`/admin/readings/${selected.id}/diff`);
    setDiff(d);
    setView('diff');
  }

  async function loadSignals() {
    if (!selected) return;
    const s = await apiGet(`/admin/readings/${selected.id}/signals`);
    setSignals(s);
    setView('signals');
  }

  async function handleRegenerate() {
    if (!selected) return;
    await apiPost(`/admin/readings/${selected.id}/regenerate`, { mode: regenMode });
    loadReadings();
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-xl text-accent">Readings</h1>
        <select value={filter} onChange={(e) => setFilter(e.target.value)} className="bg-surface border border-text-ghost rounded px-2 py-1 text-xs text-text-primary">
          {STATUSES.map((s) => <option key={s} value={s}>{s || 'All'}</option>)}
        </select>
      </div>

      <div className="flex gap-4">
        {/* List */}
        <div className="w-80 shrink-0 space-y-2 max-h-[calc(100vh-12rem)] overflow-y-auto">
          {readings.map((r) => (
            <div
              key={r.id}
              onClick={() => selectReading(r)}
              className={`bg-surface-raised border rounded p-3 cursor-pointer hover:border-text-muted ${selected?.id === r.id ? 'border-accent' : 'border-text-ghost'}`}
            >
              <div className="text-sm text-text-primary">{r.title || 'Untitled'}</div>
              <div className="flex justify-between items-center mt-1">
                <span className="text-xs text-text-muted">{r.date_context}</span>
                <span className={`text-xs px-1.5 py-0.5 rounded ${r.status === 'published' ? 'bg-green-900 text-green-300' : r.status === 'pending' ? 'bg-yellow-900 text-yellow-300' : 'bg-surface text-text-muted'}`}>
                  {r.status}
                </span>
              </div>
            </div>
          ))}
          {readings.length === 0 && <p className="text-text-muted text-sm">No readings.</p>}
        </div>

        {/* Detail */}
        {detail && (
          <div className="flex-1">
            {/* Action bar */}
            <div className="flex gap-2 mb-4 flex-wrap">
              <button onClick={() => setView('detail')} className={`text-xs px-3 py-1 rounded ${view === 'detail' ? 'bg-accent/20 text-accent' : 'bg-surface-raised text-text-muted'}`}>Detail</button>
              <button onClick={() => { setView('edit'); }} className={`text-xs px-3 py-1 rounded ${view === 'edit' ? 'bg-accent/20 text-accent' : 'bg-surface-raised text-text-muted'}`}>Edit</button>
              <button onClick={loadDiff} className={`text-xs px-3 py-1 rounded ${view === 'diff' ? 'bg-accent/20 text-accent' : 'bg-surface-raised text-text-muted'}`}>Diff</button>
              <button onClick={loadSignals} className={`text-xs px-3 py-1 rounded ${view === 'signals' ? 'bg-accent/20 text-accent' : 'bg-surface-raised text-text-muted'}`}>Signals</button>
              <div className="flex-1" />
              {['approved', 'rejected', 'published', 'archived'].map((s) => (
                <button key={s} onClick={() => handleStatusChange(s)} className={`text-xs px-2 py-1 rounded border ${detail.status === s ? 'border-accent text-accent' : 'border-text-ghost text-text-muted hover:border-text-muted'}`}>
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                </button>
              ))}
            </div>

            <div className="bg-surface-raised border border-text-ghost rounded p-4">
              {view === 'detail' && (
                <div>
                  <h2 className="text-lg text-text-primary mb-2">{(detail.generated_standard || {}).title}</h2>
                  <div className="text-xs text-text-muted mb-4">{detail.date_context} | {detail.status}</div>
                  <div className="text-sm text-text-secondary whitespace-pre-wrap mb-4">{(detail.generated_standard || {}).body}</div>
                  {detail.editorial_notes && (
                    <div className="text-xs text-text-muted border-t border-text-ghost pt-2 mt-4">
                      <span className="text-accent">Notes:</span> {detail.editorial_notes}
                    </div>
                  )}
                  {/* Regenerate */}
                  <div className="border-t border-text-ghost pt-4 mt-4 flex items-center gap-2">
                    <select value={regenMode} onChange={(e) => setRegenMode(e.target.value)} className="bg-surface border border-text-ghost rounded px-2 py-1 text-xs text-text-primary">
                      <option value="prose_only">Prose Only</option>
                      <option value="reselect">Reselect Signals</option>
                      <option value="full_rerun">Full Rerun</option>
                    </select>
                    <button onClick={handleRegenerate} className="text-xs px-3 py-1 bg-accent/20 text-accent rounded hover:bg-accent/30">
                      Regenerate
                    </button>
                  </div>
                </div>
              )}
              {view === 'edit' && <ReadingEditor reading={detail} onSave={handleSaveContent} />}
              {view === 'diff' && diff && <DiffViewer diff={diff} />}
              {view === 'signals' && (
                <div className="space-y-2">
                  <h3 className="text-xs text-text-muted uppercase tracking-wider mb-2">Selected Signals</h3>
                  {signals.map((s) => (
                    <div key={s.id} className="bg-surface rounded p-2 text-xs">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-accent">{s.domain}</span>
                        <span className={`px-1 rounded ${s.intensity === 'major' ? 'bg-red-900/30 text-red-300' : s.intensity === 'moderate' ? 'bg-yellow-900/30 text-yellow-300' : 'bg-surface text-text-muted'}`}>{s.intensity}</span>
                        {s.was_wild_card && <span className="text-yellow-400">[WILD]</span>}
                      </div>
                      <div className="text-text-secondary">{s.summary}</div>
                      {s.entities?.length > 0 && <div className="text-text-muted mt-1">{s.entities.join(', ')}</div>}
                    </div>
                  ))}
                  {signals.length === 0 && <p className="text-text-muted text-sm">No signals for this reading.</p>}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

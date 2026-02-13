import { useState, useEffect } from 'react';
import { apiGet } from '../api/client';

const DOMAINS = ['conflict', 'diplomacy', 'economy', 'technology', 'culture', 'environment', 'social', 'anomalous', 'legal', 'health'];
const INTENSITIES = ['major', 'moderate', 'minor'];

export default function SignalsPage() {
  const [signals, setSignals] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [filters, setFilters] = useState({ date_from: '', date_to: '', domain: '', intensity: '', selected_only: false });
  const [showStats, setShowStats] = useState(false);

  useEffect(() => { loadSignals(); loadStats(); }, []);

  async function loadSignals() {
    const params = new URLSearchParams();
    if (filters.date_from) params.set('date_from', filters.date_from);
    if (filters.date_to) params.set('date_to', filters.date_to);
    if (filters.domain) params.set('domain', filters.domain);
    if (filters.intensity) params.set('intensity', filters.intensity);
    if (filters.selected_only) params.set('selected_only', 'true');
    const qs = params.toString();
    apiGet(`/admin/signals/${qs ? '?' + qs : ''}`).then(setSignals).catch(() => {});
  }

  async function loadStats() {
    apiGet('/admin/signals/stats').then(setStats).catch(() => {});
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-xl text-accent">Signals</h1>
        <button onClick={() => setShowStats(!showStats)} className="text-xs px-3 py-1 bg-surface-raised border border-text-ghost rounded text-text-muted hover:border-accent">
          {showStats ? 'Hide Stats' : 'Show Stats'}
        </button>
      </div>

      {/* Stats panel */}
      {showStats && stats && (
        <div className="bg-surface-raised border border-text-ghost rounded p-4 mb-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <h4 className="text-xs text-text-muted uppercase tracking-wider mb-2">By Domain</h4>
              <div className="space-y-1">
                {(stats.by_domain || []).map((d: any) => (
                  <div key={d.domain} className="flex justify-between text-xs">
                    <span className="text-text-secondary">{d.domain}</span>
                    <span className="text-text-primary">{d.count}</span>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <h4 className="text-xs text-text-muted uppercase tracking-wider mb-2">By Intensity</h4>
              <div className="space-y-1">
                {(stats.by_intensity || []).map((i: any) => (
                  <div key={i.intensity} className="flex justify-between text-xs">
                    <span className={`${i.intensity === 'major' ? 'text-accent' : i.intensity === 'moderate' ? 'text-text-secondary' : 'text-text-muted'}`}>{i.intensity}</span>
                    <span className="text-text-primary">{i.count}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
          {stats.total != null && (
            <div className="mt-3 pt-3 border-t border-text-ghost text-xs text-text-muted">
              Total signals: <span className="text-text-primary">{stats.total}</span>
            </div>
          )}
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-2 mb-4 flex-wrap">
        <input type="date" value={filters.date_from} onChange={(e) => setFilters({ ...filters, date_from: e.target.value })} className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary" />
        <input type="date" value={filters.date_to} onChange={(e) => setFilters({ ...filters, date_to: e.target.value })} className="bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary" />
        <select value={filters.domain} onChange={(e) => setFilters({ ...filters, domain: e.target.value })} className="bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary">
          <option value="">All domains</option>
          {DOMAINS.map((d) => <option key={d}>{d}</option>)}
        </select>
        <select value={filters.intensity} onChange={(e) => setFilters({ ...filters, intensity: e.target.value })} className="bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary">
          <option value="">All intensities</option>
          {INTENSITIES.map((i) => <option key={i}>{i}</option>)}
        </select>
        <label className="flex items-center gap-1 text-xs text-text-muted">
          <input type="checkbox" checked={filters.selected_only} onChange={(e) => setFilters({ ...filters, selected_only: e.target.checked })} />
          Selected only
        </label>
        <button onClick={loadSignals} className="text-xs px-3 py-1 bg-accent/20 text-accent rounded">Filter</button>
      </div>

      {/* Signal list */}
      <div className="space-y-2">
        {signals.map((s) => (
          <div key={s.id} className="bg-surface-raised border border-text-ghost rounded p-3">
            <div className="flex justify-between items-start">
              <div className="flex-1 mr-4">
                <div className="text-sm text-text-primary">{s.summary || s.headline}</div>
                {s.headline && s.summary && s.headline !== s.summary && (
                  <div className="text-xs text-text-muted mt-1">{s.headline}</div>
                )}
                <div className="flex gap-2 mt-2 flex-wrap">
                  <span className="text-xs px-2 py-0.5 rounded bg-surface text-text-secondary">{s.domain}</span>
                  <span className={`text-xs px-2 py-0.5 rounded ${s.intensity === 'major' ? 'bg-accent/20 text-accent' : s.intensity === 'moderate' ? 'bg-surface text-text-secondary' : 'bg-surface text-text-muted'}`}>
                    {s.intensity}
                  </span>
                  {s.selected && <span className="text-xs px-2 py-0.5 rounded bg-green-900/30 text-green-400">selected</span>}
                  {s.source_name && <span className="text-xs text-text-ghost">{s.source_name}</span>}
                </div>
                {s.entities && s.entities.length > 0 && (
                  <div className="flex gap-1 mt-2 flex-wrap">
                    {s.entities.map((ent: string, i: number) => (
                      <span key={i} className="text-xs px-1.5 py-0.5 rounded bg-void text-text-muted">{ent}</span>
                    ))}
                  </div>
                )}
              </div>
              <div className="text-right shrink-0 text-xs">
                <div className="text-text-muted">{s.created_at ? new Date(s.created_at).toLocaleDateString() : ''}</div>
                {s.quality_score != null && <div className="text-text-ghost mt-1">q={s.quality_score.toFixed(2)}</div>}
                {s.thread_id && <div className="text-text-ghost mt-1 font-mono">t:{s.thread_id.slice(0, 6)}</div>}
              </div>
            </div>
          </div>
        ))}
        {signals.length === 0 && <p className="text-text-muted text-sm">No signals found.</p>}
      </div>
    </div>
  );
}

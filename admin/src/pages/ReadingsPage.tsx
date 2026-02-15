import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { apiGet, apiPatch, apiPost } from '../api/client';
import { useToast } from '../components/ui/ToastProvider';
import ConfirmDialog from '../components/ui/ConfirmDialog';
import Spinner from '../components/ui/Spinner';
import ReadingEditor from '../components/readings/ReadingEditor';
import DiffViewer from '../components/readings/DiffViewer';

const STATUSES = ['', 'pending', 'approved', 'rejected', 'published', 'archived'];

type RegenTrackingState = {
  readingId: string;
  dateContext: string;
  mode: string;
  knownRunIds: string[];
  startedAtMs: number;
  runId?: string;
  timedOut?: boolean;
};

export default function ReadingsPage() {
  const [readings, setReadings] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);
  const [detail, setDetail] = useState<any>(null);
  const [signals, setSignals] = useState<any[]>([]);
  const [diff, setDiff] = useState<any>(null);
  const [filter, setFilter] = useState('');
  const [view, setView] = useState<'detail' | 'edit' | 'diff' | 'signals'>('detail');
  const [regenMode, setRegenMode] = useState('prose_only');
  const [loading, setLoading] = useState(true);
  const [regenConfirm, setRegenConfirm] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [regenTracking, setRegenTracking] = useState<RegenTrackingState | null>(null);
  const { toast } = useToast();

  useEffect(() => {
    loadReadings();
  }, [filter]);

  useEffect(() => {
    if (!regenTracking || regenTracking.runId || regenTracking.timedOut) return;

    const poll = async () => {
      try {
        const runs = await apiGet('/admin/pipeline/runs');
        if (!Array.isArray(runs)) return;
        const knownIds = new Set(regenTracking.knownRunIds);
        const preferredMatch = runs.find(
          (run: any) =>
            run?.date_context === regenTracking.dateContext &&
            run?.regeneration_mode === regenTracking.mode &&
            typeof run?.id === 'string' &&
            !knownIds.has(run.id),
        );
        const fallbackMatch = runs.find(
          (run: any) =>
            run?.date_context === regenTracking.dateContext &&
            typeof run?.id === 'string' &&
            !knownIds.has(run.id),
        );
        const match = preferredMatch || fallbackMatch;
        if (match?.id) {
          setRegenTracking((prev) => (prev ? { ...prev, runId: match.id } : prev));
          return;
        }
        if (Date.now() - regenTracking.startedAtMs > 120000) {
          setRegenTracking((prev) => (prev ? { ...prev, timedOut: true } : prev));
        }
      } catch {
        // Keep polling while tracking is active.
      }
    };

    void poll();
    const timer = window.setInterval(() => {
      void poll();
    }, 5000);
    return () => window.clearInterval(timer);
  }, [regenTracking]);

  async function loadReadings() {
    setLoading(true);
    const params = filter ? `?status=${filter}` : '';
    try {
      const data = await apiGet(`/admin/readings/${params}`);
      setReadings(data);
    } catch (e: any) {
      toast.error(e.message);
    }
    setLoading(false);
  }

  async function selectReading(r: any) {
    setSelected(r);
    setView('detail');
    try {
      const d = await apiGet(`/admin/readings/${r.id}`);
      setDetail(d);
    } catch (e: any) {
      toast.error(e.message);
    }
  }

  async function handleStatusChange(status: string) {
    if (!selected) return;
    try {
      await apiPatch(`/admin/readings/${selected.id}`, { status });
      setReadings(readings.map((r) => r.id === selected.id ? { ...r, status } : r));
      if (detail) setDetail({ ...detail, status });
      toast.success(`Status changed to ${status}`);
    } catch (e: any) {
      toast.error(e.message);
    }
  }

  async function handleSaveContent(data: any) {
    if (!selected) return;
    try {
      await apiPatch(`/admin/readings/${selected.id}/content`, data);
      const d = await apiGet(`/admin/readings/${selected.id}`);
      setDetail(d);
      toast.success('Content saved');
    } catch (e: any) {
      toast.error(e.message);
    }
  }

  async function loadDiff() {
    if (!selected) return;
    try {
      const d = await apiGet(`/admin/readings/${selected.id}/diff`);
      setDiff(d);
      setView('diff');
    } catch (e: any) {
      toast.error(e.message);
    }
  }

  async function loadSignals() {
    if (!selected) return;
    try {
      const s = await apiGet(`/admin/readings/${selected.id}/signals`);
      setSignals(s);
      setView('signals');
    } catch (e: any) {
      toast.error(e.message);
    }
  }

  async function handleRegenerate() {
    const activeReading = selected;
    setRegenConfirm(false);
    if (!activeReading) return;
    setRegenerating(true);
    setRegenTracking(null);
    try {
      let knownRunIds: string[] = [];
      try {
        const existingRuns = await apiGet('/admin/pipeline/runs');
        if (Array.isArray(existingRuns)) {
          knownRunIds = existingRuns
            .filter((run: any) => run?.date_context === activeReading.date_context && typeof run?.id === 'string')
            .map((run: any) => run.id);
        }
      } catch {
        knownRunIds = [];
      }

      const response = await apiPost(`/admin/readings/${activeReading.id}/regenerate`, {
        mode: regenMode,
        wait_for_completion: false,
      });
      if (response?.mode === 'background' || response?.status === 'started') {
        const trackingDate = response?.date_context || activeReading.date_context;
        setRegenTracking({
          readingId: activeReading.id,
          dateContext: trackingDate,
          mode: regenMode,
          knownRunIds,
          startedAtMs: Date.now(),
        });
        toast.success(`Regeneration started (${regenMode})`);
      } else if (response?.run_id) {
        setRegenTracking({
          readingId: activeReading.id,
          dateContext: activeReading.date_context,
          mode: regenMode,
          knownRunIds,
          startedAtMs: Date.now(),
          runId: response.run_id,
        });
        toast.success('Regeneration completed');
      } else {
        toast.success('Regeneration completed');
      }
      await loadReadings();
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setRegenerating(false);
    }
  }

  const standard = detail ? (detail.published_standard || detail.generated_standard || {}) : {};
  const extended = detail ? (detail.published_extended || detail.generated_extended || {}) : {};
  const sections = Array.isArray(extended.sections) ? extended.sections : [];
  const annotations = detail ? (detail.published_annotations || detail.generated_annotations || []) : [];

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-xl text-accent">Readings</h1>
        <select value={filter} onChange={(e) => setFilter(e.target.value)} className="bg-surface border border-text-ghost rounded px-2 py-1 text-xs text-text-primary">
          {STATUSES.map((s) => <option key={s} value={s}>{s || 'All'}</option>)}
        </select>
      </div>

      {regenTracking && (
        <div className="mb-4 bg-surface-raised border border-text-ghost rounded p-3 text-xs text-text-secondary flex flex-wrap items-center gap-3">
          <div className="flex-1 min-w-[16rem]">
            {regenTracking.runId ? (
              <span>
                Regeneration run is available for {regenTracking.dateContext}.{" "}
                <Link
                  to={`/pipeline?run=${encodeURIComponent(regenTracking.runId)}`}
                  className="text-accent hover:underline"
                >
                  Open run {regenTracking.runId.slice(0, 8)}
                </Link>
              </span>
            ) : regenTracking.timedOut ? (
              <span>
                Regeneration started for {regenTracking.dateContext}, but the run is not visible yet. Check Pipeline shortly.
              </span>
            ) : (
              <span>
                Regeneration started for {regenTracking.dateContext}. Waiting for pipeline run record...
              </span>
            )}
          </div>
          <button
            onClick={() => setRegenTracking(null)}
            className="text-[11px] text-text-muted hover:text-text-primary"
          >
            Dismiss
          </button>
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-12"><Spinner /></div>
      ) : (
        <div className="flex flex-col lg:flex-row gap-4">
          {/* List */}
          <div className="w-full lg:w-80 shrink-0 space-y-2 max-h-[calc(100vh-12rem)] overflow-y-auto">
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
                    <h2 className="text-lg text-text-primary mb-2">{standard.title || 'Untitled Reading'}</h2>
                    <div className="text-xs text-text-muted mb-4">{detail.date_context} | {detail.status}</div>

                    <div className="mb-6">
                      <div className="text-xs text-text-muted uppercase tracking-wider mb-2">Standard Reading</div>
                      <div className="text-sm text-text-secondary whitespace-pre-wrap mb-2">{standard.body || '(empty)'}</div>
                      {standard.word_count ? (
                        <div className="text-[11px] text-text-muted">{standard.word_count} words</div>
                      ) : null}
                    </div>

                    <div className="mb-6 border-t border-text-ghost pt-4">
                      <div className="text-xs text-text-muted uppercase tracking-wider mb-2">Extended Reading</div>
                      {extended.title ? <div className="text-sm text-text-primary mb-1">{extended.title}</div> : null}
                      {extended.subtitle ? <div className="text-xs text-text-muted mb-3">{extended.subtitle}</div> : null}
                      {sections.length > 0 ? (
                        <div className="space-y-3">
                          {sections.map((section: any, index: number) => (
                            <div key={index} className="bg-surface rounded p-3">
                              {section.heading ? <div className="text-xs text-accent mb-1">{section.heading}</div> : null}
                              <div className="text-xs text-text-secondary whitespace-pre-wrap">{section.body || '(empty section)'}</div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="text-xs text-text-muted">No extended sections.</div>
                      )}
                      {extended.word_count ? (
                        <div className="text-[11px] text-text-muted mt-2">{extended.word_count} words</div>
                      ) : null}
                    </div>

                    <div className="mb-4 border-t border-text-ghost pt-4">
                      <div className="text-xs text-text-muted uppercase tracking-wider mb-2">Transit Annotations</div>
                      {Array.isArray(annotations) && annotations.length > 0 ? (
                        <div className="space-y-2">
                          {annotations.map((annotation: any, index: number) => (
                            <div key={index} className="bg-surface rounded p-3 text-xs">
                              <div className="text-accent mb-1">{annotation.aspect || 'Untitled aspect'}</div>
                              <div className="text-text-secondary mb-1 whitespace-pre-wrap">{annotation.gloss || ''}</div>
                              {annotation.cultural_resonance ? <div className="text-text-muted whitespace-pre-wrap">Resonance: {annotation.cultural_resonance}</div> : null}
                              {annotation.temporal_arc ? <div className="text-text-muted whitespace-pre-wrap">Arc: {annotation.temporal_arc}</div> : null}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="text-xs text-text-muted">No annotations.</div>
                      )}
                    </div>

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
                      <button
                        onClick={() => setRegenConfirm(true)}
                        disabled={regenerating}
                        className="text-xs px-3 py-1 bg-accent/20 text-accent rounded hover:bg-accent/30 disabled:opacity-50"
                      >
                        {regenerating ? 'Starting...' : 'Regenerate'}
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
      )}

      <ConfirmDialog
        open={regenConfirm}
        title="Regenerate Reading"
        message={`This will regenerate the reading using mode: ${regenMode}. Continue?`}
        onConfirm={handleRegenerate}
        onCancel={() => setRegenConfirm(false)}
        confirmLabel={regenerating ? 'Starting...' : 'Confirm'}
        confirmDisabled={regenerating}
        cancelDisabled={regenerating}
      />
    </div>
  );
}

import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { apiGet, apiPost, apiPut } from '../api/client';
import { useToast } from '../components/ui/ToastProvider';
import Spinner from '../components/ui/Spinner';

export default function PipelinePage() {
  const [runs, setRuns] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);
  const [artifacts, setArtifacts] = useState<any>(null);
  const [schedule, setSchedule] = useState<any>(null);
  const [scheduleForm, setScheduleForm] = useState({
    pipeline_schedule: '',
    timezone: '',
    pipeline_run_on_start: false,
    auto_publish: false,
  });
  const [savingSchedule, setSavingSchedule] = useState(false);
  const [showTrigger, setShowTrigger] = useState(false);
  const [triggerForm, setTriggerForm] = useState({ regeneration_mode: '', date_context: '', parent_run_id: '' });
  const [triggering, setTriggering] = useState(false);
  const [pendingTrigger, setPendingTrigger] = useState<{
    dateContext: string;
    knownRunIds: string[];
    startedAtMs: number;
  } | null>(null);
  const [handledRunQuery, setHandledRunQuery] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchParams, setSearchParams] = useSearchParams();
  const { toast } = useToast();
  const runQuery = searchParams.get('run');

  useEffect(() => {
    Promise.all([
      apiGet('/admin/pipeline/runs'),
      apiGet('/admin/pipeline/schedule').catch(() => null),
    ])
      .then(([runList, scheduleInfo]) => {
        setRuns(runList);
        setSchedule(scheduleInfo);
        if (scheduleInfo) {
          setScheduleForm({
            pipeline_schedule: scheduleInfo.pipeline_schedule || '',
            timezone: scheduleInfo.timezone || '',
            pipeline_run_on_start: !!scheduleInfo.pipeline_run_on_start,
            auto_publish: !!scheduleInfo.auto_publish,
          });
        }
      })
      .catch((e: any) => toast.error(e.message))
      .finally(() => setLoading(false));
  }, []);

  const loadRunById = useCallback(
    async (runId: string) => {
      const runSummary = runs.find((run) => run.id === runId);
      setSelected(runSummary || { id: runId });
      setArtifacts(null);
      try {
        const [detail, arts] = await Promise.all([
          apiGet(`/admin/pipeline/runs/${runId}`),
          apiGet(`/admin/pipeline/runs/${runId}/artifacts`),
        ]);
        setSelected(detail);
        setArtifacts(arts);
      } catch (e: any) {
        toast.error(e.message);
      }
    },
    [runs, toast],
  );

  useEffect(() => {
    if (!runQuery) {
      setHandledRunQuery(null);
      return;
    }
    if (handledRunQuery === runQuery) return;
    setHandledRunQuery(runQuery);
    void loadRunById(runQuery);
  }, [runQuery, handledRunQuery, loadRunById]);

  useEffect(() => {
    const hasRunning = runs.some((r) => r.status === 'running');
    if (!hasRunning && !pendingTrigger) return;

    const timer = window.setInterval(async () => {
      try {
        const latestRuns = await apiGet('/admin/pipeline/runs');
        setRuns(latestRuns);
        if (selected?.id) {
          const refreshed = latestRuns.find((r: any) => r.id === selected.id);
          if (refreshed) {
            setSelected((prev: any) => ({ ...prev, ...refreshed }));
          }
        }

        if (pendingTrigger) {
          const newRunAppeared = latestRuns.some(
            (r: any) => r.date_context === pendingTrigger.dateContext && !pendingTrigger.knownRunIds.includes(r.id),
          );
          const timedOut = Date.now() - pendingTrigger.startedAtMs > 45000;
          if (newRunAppeared || timedOut) {
            setPendingTrigger(null);
            if (timedOut) {
              toast.info('Trigger accepted, but no new run is visible yet. Check logs if this persists.');
            }
          }
        }
      } catch {
        // Quiet retry loop while a run is active.
      }
    }, 5000);

    return () => window.clearInterval(timer);
  }, [runs, selected?.id, pendingTrigger, toast]);

  async function triggerPipeline() {
    setTriggering(true);
    const knownRunIds = runs.map((r) => r.id);
    try {
      const body: any = {};
      if (triggerForm.regeneration_mode) body.regeneration_mode = triggerForm.regeneration_mode;
      if (triggerForm.date_context) body.date_context = triggerForm.date_context;
      if (triggerForm.parent_run_id) body.parent_run_id = triggerForm.parent_run_id;
      body.wait_for_completion = false;
      const response = await apiPost('/admin/pipeline/trigger', body);
      setShowTrigger(false);
      const latestRuns = await apiGet('/admin/pipeline/runs');
      setRuns(latestRuns);
      if (response?.mode === 'background') {
        const triggerDate = response.date_context || triggerForm.date_context || new Date().toISOString().slice(0, 10);
        const newRunVisible = latestRuns.some(
          (r: any) => r.date_context === triggerDate && !knownRunIds.includes(r.id),
        );
        if (!newRunVisible) {
          setPendingTrigger({ dateContext: triggerDate, knownRunIds, startedAtMs: Date.now() });
        } else {
          setPendingTrigger(null);
        }
        toast.success(`Pipeline started for ${response.date_context}. Status will update automatically.`);
      } else if (response?.run_id) {
        setPendingTrigger(null);
        toast.success(`Pipeline completed. Run ID: ${response.run_id}`);
      } else {
        setPendingTrigger(null);
        toast.success('Pipeline finished');
      }
    } catch (e: any) {
      setPendingTrigger(null);
      toast.error(e.message);
    } finally {
      setTriggering(false);
    }
  }

  async function saveSchedule() {
    setSavingSchedule(true);
    try {
      await apiPut('/admin/pipeline/schedule', scheduleForm);
      const updated = await apiGet('/admin/pipeline/schedule');
      setSchedule(updated);
      setScheduleForm({
        pipeline_schedule: updated.pipeline_schedule || '',
        timezone: updated.timezone || '',
        pipeline_run_on_start: !!updated.pipeline_run_on_start,
        auto_publish: !!updated.auto_publish,
      });
      toast.success('Scheduler settings saved');
    } catch (e: any) {
      toast.error(e.message);
    }
    setSavingSchedule(false);
  }

  async function selectRun(run: any) {
    setHandledRunQuery(run.id);
    const next = new URLSearchParams(searchParams);
    next.set('run', run.id);
    setSearchParams(next, { replace: true });
    await loadRunById(run.id);
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-xl text-accent">Pipeline</h1>
        <button onClick={() => setShowTrigger(!showTrigger)} className="text-xs px-3 py-1 bg-surface-raised border border-text-ghost rounded text-accent hover:border-accent">
          Trigger Run
        </button>
      </div>

      {schedule && (
        <div className="bg-surface-raised border border-text-ghost rounded p-3 mb-4 text-xs space-y-2">
          <div className="flex justify-between items-center">
            <div className="text-text-secondary">Run Schedule</div>
            <span className="text-[11px] text-text-muted">Source: {schedule.source}</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-2">
            <input
              value={scheduleForm.pipeline_schedule}
              onChange={(e) => setScheduleForm({ ...scheduleForm, pipeline_schedule: e.target.value })}
              placeholder="0 5 * * *"
              className="bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary font-mono"
              title="Daily cron format only: M H * * *"
            />
            <input
              value={scheduleForm.timezone}
              onChange={(e) => setScheduleForm({ ...scheduleForm, timezone: e.target.value })}
              placeholder="America/New_York"
              className="bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary font-mono"
            />
            <label className="flex items-center gap-2 text-text-muted bg-surface border border-text-ghost rounded px-2 py-1">
              <input
                type="checkbox"
                checked={scheduleForm.pipeline_run_on_start}
                onChange={(e) => setScheduleForm({ ...scheduleForm, pipeline_run_on_start: e.target.checked })}
              />
              run once on pipeline container start
            </label>
            <label className="flex items-center gap-2 text-text-muted bg-surface border border-text-ghost rounded px-2 py-1">
              <input
                type="checkbox"
                checked={scheduleForm.auto_publish}
                onChange={(e) => setScheduleForm({ ...scheduleForm, auto_publish: e.target.checked })}
              />
              auto-publish scheduler runs
            </label>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={saveSchedule}
              disabled={savingSchedule}
              className="text-xs px-3 py-1 bg-accent/20 text-accent rounded hover:bg-accent/30 disabled:opacity-50"
            >
              {savingSchedule ? 'Saving...' : 'Save Schedule'}
            </button>
            {schedule.next_run_at && (
              <span className="text-text-muted">Next run: {new Date(schedule.next_run_at).toLocaleString()}</span>
            )}
          </div>
          {schedule.parse_error && <div className="text-red-400">Schedule error: {schedule.parse_error}</div>}
          <div className="text-text-muted">
            UI values are stored in DB and override env defaults.
            Env fallback remains in <span className="font-mono">.env</span> via <span className="font-mono">PIPELINE_SCHEDULE</span>/<span className="font-mono">TIMEZONE</span>.
          </div>
          <div className="text-text-muted">
            Scheduler runs auto-publish only when enabled; manual/regeneration/event runs stay pending in the reading queue until published from Readings.
          </div>
        </div>
      )}

      {/* Trigger modal */}
      {showTrigger && (
        <div className="bg-surface-raised border border-text-ghost rounded p-4 mb-4 space-y-3">
          <div className="text-xs text-text-muted">
            Manual runs start in background and this page auto-refreshes every 5 seconds while a run is active.
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="text-xs text-text-muted block mb-1">Regeneration Mode</label>
              <select value={triggerForm.regeneration_mode} onChange={(e) => setTriggerForm({ ...triggerForm, regeneration_mode: e.target.value })} className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary">
                <option value="">Normal (new run)</option>
                <option value="prose_only">Prose Only</option>
                <option value="reselect">Reselect Signals</option>
                <option value="full_rerun">Full Rerun</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-text-muted block mb-1">Date Context</label>
              <input type="date" value={triggerForm.date_context} onChange={(e) => setTriggerForm({ ...triggerForm, date_context: e.target.value })} className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary" />
            </div>
            <div>
              <label className="text-xs text-text-muted block mb-1">Parent Run ID</label>
              <input value={triggerForm.parent_run_id} onChange={(e) => setTriggerForm({ ...triggerForm, parent_run_id: e.target.value })} placeholder="optional" className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary" />
            </div>
          </div>
          <button onClick={triggerPipeline} disabled={triggering} className="text-xs px-3 py-1 bg-accent/20 text-accent rounded hover:bg-accent/30 disabled:opacity-50">
            {triggering ? 'Starting background run...' : 'Start Pipeline'}
          </button>
        </div>
      )}

      {pendingTrigger && (
        <div className="bg-surface-raised border border-text-ghost rounded p-3 mb-4 text-xs text-text-muted">
          Trigger accepted for <span className="text-text-primary">{pendingTrigger.dateContext}</span>. Waiting for the new run record to appear...
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-12"><Spinner /></div>
      ) : (
        <div className="flex flex-col lg:flex-row gap-4">
          {/* Run list */}
          <div className="w-full lg:w-80 shrink-0 space-y-2">
            {runs.map((r) => (
              <div
                key={r.id}
                onClick={() => selectRun(r)}
                className={`bg-surface-raised border rounded p-3 cursor-pointer hover:border-text-muted ${selected?.id === r.id ? 'border-accent' : 'border-text-ghost'}`}
              >
                <div className="flex justify-between">
                  <span className="text-sm text-text-primary">{r.date_context}</span>
                  <span className={`text-xs ${r.status === 'completed' ? 'text-green-400' : r.status === 'failed' ? 'text-red-400' : 'text-yellow-400'}`}>{r.status}</span>
                </div>
                <div className="text-xs text-text-muted">
                  Run #{r.run_number}
                  {r.regeneration_mode && <span className="ml-2 text-accent">{r.regeneration_mode}</span>}
                </div>
                <div className="text-[11px] text-text-ghost mt-1">Source: {r.trigger_source || 'scheduler'}</div>
                {r.progress_hint && <div className="text-xs text-text-muted mt-1">{r.progress_hint}</div>}
                {typeof r.elapsed_seconds === 'number' && (
                  <div className="text-[11px] text-text-ghost mt-1">
                    Elapsed: {Math.floor(r.elapsed_seconds / 60)}m {r.elapsed_seconds % 60}s
                  </div>
                )}
                {r.reading_status && (
                  <div className="text-[11px] text-text-muted mt-1">
                    Reading: <span className={r.reading_status === 'published' ? 'text-green-400' : 'text-yellow-400'}>{r.reading_status}</span>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Run detail */}
          {selected && (
            <div className="flex-1 bg-surface-raised border border-text-ghost rounded p-4">
              <h3 className="text-sm text-accent mb-3">Run Detail: {selected.date_context} #{selected.run_number}</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs mb-4">
                <div><span className="text-text-muted">Status:</span> <span className="text-text-primary">{selected.status}</span></div>
                {selected.progress_hint && <div><span className="text-text-muted">Progress:</span> <span className="text-text-secondary">{selected.progress_hint}</span></div>}
                <div><span className="text-text-muted">Source:</span> <span className="text-text-primary">{selected.trigger_source || 'scheduler'}</span></div>
                <div><span className="text-text-muted">Seed:</span> <span className="text-text-primary font-mono">{selected.seed}</span></div>
                <div><span className="text-text-muted">Code:</span> <span className="text-text-primary font-mono">{selected.code_version}</span></div>
                <div><span className="text-text-muted">Started:</span> <span className="text-text-primary">{selected.started_at ? new Date(selected.started_at).toLocaleString() : '-'}</span></div>
                {typeof selected.elapsed_seconds === 'number' && <div><span className="text-text-muted">Elapsed:</span> <span className="text-text-primary">{Math.floor(selected.elapsed_seconds / 60)}m {selected.elapsed_seconds % 60}s</span></div>}
                {selected.reading_status && (
                  <div>
                    <span className="text-text-muted">Reading:</span>{" "}
                    <span className={selected.reading_status === 'published' ? 'text-green-400' : 'text-yellow-400'}>
                      {selected.reading_status}
                    </span>
                  </div>
                )}
                {selected.reading_published_at && (
                  <div>
                    <span className="text-text-muted">Published:</span>{" "}
                    <span className="text-text-primary">{new Date(selected.reading_published_at).toLocaleString()}</span>
                  </div>
                )}
                {selected.error_detail && <div className="col-span-full text-red-400">Error: {selected.error_detail}</div>}
              </div>

              {/* Settings snapshot */}
              {selected.model_config_json && Object.keys(selected.model_config_json).length > 0 && (
                <details className="mb-3">
                  <summary className="text-xs text-text-muted cursor-pointer">Pipeline Settings Snapshot</summary>
                  <pre className="text-xs text-text-secondary mt-1 overflow-auto max-h-40 bg-surface rounded p-2">{JSON.stringify(selected.model_config_json, null, 2)}</pre>
                </details>
              )}

              {artifacts && (
                <>
                  {artifacts.selected_signals?.length > 0 && (
                    <details className="mb-3">
                      <summary className="text-xs text-text-muted cursor-pointer">Selected Signals ({artifacts.selected_signals.length})</summary>
                      <div className="mt-1 space-y-1">
                        {artifacts.selected_signals.map((s: any, i: number) => (
                          <div key={i} className="text-xs text-text-secondary bg-surface rounded p-2">
                            <span className="text-accent">[{s.domain}]</span> {s.summary}
                            {s.was_wild_card && <span className="ml-1 text-yellow-400">[WILD]</span>}
                          </div>
                        ))}
                      </div>
                    </details>
                  )}
                  {artifacts.prompt_payloads && Object.keys(artifacts.prompt_payloads).length > 0 && (
                    <details className="mb-3">
                      <summary className="text-xs text-text-muted cursor-pointer">Prompt Payloads</summary>
                      {Object.entries(artifacts.prompt_payloads).map(([key, val]: [string, any]) => (
                        <details key={key} className="ml-4 mt-1">
                          <summary className="text-xs text-text-muted cursor-pointer">{key}</summary>
                          <pre className="text-xs text-text-secondary overflow-auto max-h-32 bg-surface rounded p-2 mt-1">{typeof val === 'string' ? val : JSON.stringify(val, null, 2)}</pre>
                        </details>
                      ))}
                    </details>
                  )}
                  {artifacts.interpretive_plan && (
                    <details className="mb-3">
                      <summary className="text-xs text-text-muted cursor-pointer">Interpretive Plan</summary>
                      <pre className="text-xs text-text-secondary overflow-auto max-h-40 bg-surface rounded p-2 mt-1">{JSON.stringify(artifacts.interpretive_plan, null, 2)}</pre>
                    </details>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

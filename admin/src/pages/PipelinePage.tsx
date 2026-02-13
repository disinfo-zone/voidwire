import { useState, useEffect } from 'react';
import { apiGet, apiPost } from '../api/client';

export default function PipelinePage() {
  const [runs, setRuns] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);
  const [artifacts, setArtifacts] = useState<any>(null);
  const [showTrigger, setShowTrigger] = useState(false);
  const [triggerForm, setTriggerForm] = useState({ regeneration_mode: '', date_context: '', parent_run_id: '' });
  const [triggering, setTriggering] = useState(false);

  useEffect(() => {
    apiGet('/admin/pipeline/runs').then(setRuns).catch(() => {});
  }, []);

  async function triggerPipeline() {
    setTriggering(true);
    try {
      const body: any = {};
      if (triggerForm.regeneration_mode) body.regeneration_mode = triggerForm.regeneration_mode;
      if (triggerForm.date_context) body.date_context = triggerForm.date_context;
      if (triggerForm.parent_run_id) body.parent_run_id = triggerForm.parent_run_id;
      await apiPost('/admin/pipeline/trigger', body);
      setShowTrigger(false);
      setRuns(await apiGet('/admin/pipeline/runs'));
    } catch (err) {
      console.error('Trigger failed:', err);
    }
    setTriggering(false);
  }

  async function selectRun(run: any) {
    setSelected(run);
    setArtifacts(null);
    try {
      const [detail, arts] = await Promise.all([
        apiGet(`/admin/pipeline/runs/${run.id}`),
        apiGet(`/admin/pipeline/runs/${run.id}/artifacts`),
      ]);
      setSelected(detail);
      setArtifacts(arts);
    } catch {}
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-xl text-accent">Pipeline</h1>
        <button onClick={() => setShowTrigger(!showTrigger)} className="text-xs px-3 py-1 bg-surface-raised border border-text-ghost rounded text-accent hover:border-accent">
          Trigger Run
        </button>
      </div>

      {/* Trigger modal */}
      {showTrigger && (
        <div className="bg-surface-raised border border-text-ghost rounded p-4 mb-4 space-y-3">
          <div className="grid grid-cols-3 gap-3">
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
            {triggering ? 'Running...' : 'Start Pipeline'}
          </button>
        </div>
      )}

      <div className="flex gap-4">
        {/* Run list */}
        <div className="w-80 shrink-0 space-y-2">
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
            </div>
          ))}
        </div>

        {/* Run detail */}
        {selected && (
          <div className="flex-1 bg-surface-raised border border-text-ghost rounded p-4">
            <h3 className="text-sm text-accent mb-3">Run Detail: {selected.date_context} #{selected.run_number}</h3>
            <div className="grid grid-cols-2 gap-3 text-xs mb-4">
              <div><span className="text-text-muted">Status:</span> <span className="text-text-primary">{selected.status}</span></div>
              <div><span className="text-text-muted">Seed:</span> <span className="text-text-primary font-mono">{selected.seed}</span></div>
              <div><span className="text-text-muted">Code:</span> <span className="text-text-primary font-mono">{selected.code_version}</span></div>
              <div><span className="text-text-muted">Started:</span> <span className="text-text-primary">{selected.started_at ? new Date(selected.started_at).toLocaleString() : '-'}</span></div>
              {selected.error_detail && <div className="col-span-2 text-red-400">Error: {selected.error_detail}</div>}
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
    </div>
  );
}

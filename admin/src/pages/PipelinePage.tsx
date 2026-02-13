import { useState, useEffect } from 'react';
import { apiGet, apiPost } from '../api/client';

export default function PipelinePage() {
  const [runs, setRuns] = useState<any[]>([]);

  useEffect(() => {
    apiGet('/admin/pipeline/runs').then(setRuns).catch(() => {});
  }, []);

  async function triggerPipeline() {
    await apiPost('/admin/pipeline/trigger', {});
    setRuns(await apiGet('/admin/pipeline/runs'));
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-xl text-accent">Pipeline</h1>
        <button onClick={triggerPipeline} className="text-xs px-3 py-1 bg-surface-raised border border-text-ghost rounded text-accent hover:border-accent">
          Trigger Run
        </button>
      </div>
      <div className="space-y-2">
        {runs.map(r => (
          <div key={r.id} className="bg-surface-raised border border-text-ghost rounded p-3 flex justify-between">
            <div>
              <span className="text-sm text-text-primary">{r.date_context}</span>
              <span className="text-xs text-text-muted ml-2">Run #{r.run_number}</span>
            </div>
            <span className={`text-xs ${r.status === 'completed' ? 'text-green-400' : r.status === 'failed' ? 'text-red-400' : 'text-yellow-400'}`}>{r.status}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

import { useState, useEffect } from 'react';
import { apiGet, apiPost } from '../api/client';

export default function DashboardPage() {
  const [health, setHealth] = useState<any>(null);
  const [pipelineHealth, setPipelineHealth] = useState<any[]>([]);
  const [latestReading, setLatestReading] = useState<any>(null);
  const [llmSlots, setLlmSlots] = useState<any[]>([]);
  const [threadCount, setThreadCount] = useState<number | null>(null);
  const [sourceHealth, setSourceHealth] = useState<{ total: number; active: number; errored: number } | null>(null);
  const [triggering, setTriggering] = useState(false);

  useEffect(() => {
    apiGet('/health').then(setHealth).catch(() => {});
    apiGet('/admin/analytics/pipeline-health?days=7').then(setPipelineHealth).catch(() => {});
    apiGet('/admin/readings/?limit=1').then((readings) => {
      if (Array.isArray(readings) && readings.length > 0) setLatestReading(readings[0]);
    }).catch(() => {});
    apiGet('/admin/llm/').then(setLlmSlots).catch(() => {});
    apiGet('/admin/threads/?active=true').then((threads) => {
      setThreadCount(Array.isArray(threads) ? threads.length : 0);
    }).catch(() => {});
    apiGet('/admin/sources/').then((sources) => {
      if (Array.isArray(sources)) {
        setSourceHealth({
          total: sources.length,
          active: sources.filter((s: any) => s.status === 'active').length,
          errored: sources.filter((s: any) => s.last_error).length,
        });
      }
    }).catch(() => {});
  }, []);

  async function triggerPipeline() {
    setTriggering(true);
    try {
      await apiPost('/admin/pipeline/trigger', {});
    } catch {}
    setTriggering(false);
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-xl text-accent">Dashboard</h1>
        <button
          onClick={triggerPipeline}
          disabled={triggering}
          className="text-xs px-4 py-2 bg-accent/20 text-accent rounded hover:bg-accent/30 disabled:opacity-50"
        >
          {triggering ? 'Triggering...' : 'Trigger Pipeline'}
        </button>
      </div>

      {/* Status cards */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="bg-surface-raised border border-text-ghost rounded p-4">
          <div className="text-xs text-text-muted uppercase tracking-wider mb-2">API Status</div>
          <div className={`text-sm ${health?.status === 'ok' ? 'text-green-400' : 'text-red-400'}`}>
            {health?.status || 'checking...'}
          </div>
        </div>

        <div className="bg-surface-raised border border-text-ghost rounded p-4">
          <div className="text-xs text-text-muted uppercase tracking-wider mb-2">Active Threads</div>
          <div className="text-sm text-text-primary">{threadCount != null ? threadCount : '...'}</div>
        </div>

        <div className="bg-surface-raised border border-text-ghost rounded p-4">
          <div className="text-xs text-text-muted uppercase tracking-wider mb-2">Sources</div>
          {sourceHealth ? (
            <div className="text-sm">
              <span className="text-text-primary">{sourceHealth.active}/{sourceHealth.total} active</span>
              {sourceHealth.errored > 0 && <span className="text-red-400 ml-2">{sourceHealth.errored} errored</span>}
            </div>
          ) : (
            <div className="text-sm text-text-muted">...</div>
          )}
        </div>

        <div className="bg-surface-raised border border-text-ghost rounded p-4">
          <div className="text-xs text-text-muted uppercase tracking-wider mb-2">Pipeline (7d)</div>
          <div className="text-sm text-text-primary">
            {pipelineHealth.map((item) => (
              <span key={item.status} className="mr-3">
                <span className={item.status === 'completed' ? 'text-green-400' : item.status === 'failed' ? 'text-red-400' : 'text-text-muted'}>{item.count}</span>
                <span className="text-text-ghost text-xs ml-1">{item.status}</span>
              </span>
            ))}
            {pipelineHealth.length === 0 && <span className="text-text-muted">No runs</span>}
          </div>
        </div>
      </div>

      {/* LLM Slot Health */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        {llmSlots.map((slot) => (
          <div key={slot.slot} className="bg-surface-raised border border-text-ghost rounded p-4">
            <div className="flex justify-between items-center mb-2">
              <span className="text-xs text-text-muted uppercase tracking-wider">{slot.slot}</span>
              <span className={`w-2 h-2 rounded-full ${slot.active ? 'bg-green-400' : 'bg-text-ghost'}`} />
            </div>
            <div className="text-sm text-text-primary">{slot.provider || 'Not configured'}</div>
            <div className="text-xs text-text-muted mt-1">{slot.model_id || '-'}</div>
            {slot.api_key_set && <div className="text-xs text-green-400 mt-1">Key set</div>}
            {!slot.api_key_set && slot.active && <div className="text-xs text-red-400 mt-1">No API key</div>}
          </div>
        ))}
        {llmSlots.length === 0 && (
          <div className="col-span-3 bg-surface-raised border border-text-ghost rounded p-4 text-sm text-text-muted">
            No LLM slots configured.
          </div>
        )}
      </div>

      {/* Latest reading preview */}
      {latestReading && (
        <div className="bg-surface-raised border border-text-ghost rounded p-4 mb-6">
          <div className="flex justify-between items-center mb-2">
            <h3 className="text-xs text-text-muted uppercase tracking-wider">Latest Reading</h3>
            <div className="flex items-center gap-2">
              <span className={`text-xs ${latestReading.status === 'published' ? 'text-green-400' : latestReading.status === 'approved' ? 'text-accent' : 'text-text-muted'}`}>
                {latestReading.status}
              </span>
              <span className="text-xs text-text-ghost">{latestReading.date_for || ''}</span>
            </div>
          </div>
          <div className="text-sm text-accent mb-1">{latestReading.title || 'Untitled'}</div>
          <div className="text-xs text-text-secondary line-clamp-3">
            {latestReading.published_standard || latestReading.generated_standard || 'No content'}
          </div>
          {latestReading.section_count != null && (
            <div className="text-xs text-text-ghost mt-2">{latestReading.section_count} sections</div>
          )}
        </div>
      )}

      {/* Quick reference */}
      <div className="text-text-muted text-xs">
        Use the sidebar to manage readings, sources, templates, threads, signals, and settings.
      </div>
    </div>
  );
}

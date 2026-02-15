import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { apiGet, apiPost } from '../api/client';
import { useToast } from '../components/ui/ToastProvider';
import Spinner from '../components/ui/Spinner';

function inferProvider(slot: any): string {
  const explicit = String(slot?.provider_name || '').trim();
  if (explicit) return explicit;
  const model = String(slot?.model_id || '').trim();
  if (!model) return '';
  const slash = model.indexOf('/');
  if (slash > 0) return model.slice(0, slash);
  return '';
}

function isSlotConfigured(slot: any): boolean {
  return (
    String(slot?.api_endpoint || '').trim().length > 0 &&
    String(slot?.model_id || '').trim().length > 0 &&
    String(slot?.api_key_masked || '').trim().length > 0
  );
}

export default function DashboardPage() {
  const [health, setHealth] = useState<any>(null);
  const [pipelineHealth, setPipelineHealth] = useState<any[]>([]);
  const [latestReading, setLatestReading] = useState<any>(null);
  const [llmSlots, setLlmSlots] = useState<any[]>([]);
  const [threadCount, setThreadCount] = useState<number | null>(null);
  const [sourceHealth, setSourceHealth] = useState<{ total: number; active: number; errored: number } | null>(null);
  const [operationalHealth, setOperationalHealth] = useState<any>(null);
  const [triggering, setTriggering] = useState(false);
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();

  useEffect(() => {
    Promise.all([
      apiGet('/health').then(setHealth),
      apiGet('/admin/analytics/pipeline-health?days=7').then(setPipelineHealth),
      apiGet('/admin/readings/?limit=1').then((readings) => {
        if (Array.isArray(readings) && readings.length > 0) setLatestReading(readings[0]);
      }),
      apiGet('/admin/llm/').then(setLlmSlots),
      apiGet('/admin/threads/?active=true').then((threads) => {
        setThreadCount(Array.isArray(threads) ? threads.length : 0);
      }),
      apiGet('/admin/sources/').then((sources) => {
        if (Array.isArray(sources)) {
          setSourceHealth({
            total: sources.length,
            active: sources.filter((s: any) => s.status === 'active').length,
            errored: sources.filter((s: any) => s.last_error).length,
          });
        }
      }),
      apiGet('/admin/analytics/operational-health').then(setOperationalHealth),
    ]).catch((e) => toast.error(e.message)).finally(() => setLoading(false));
  }, []);

  async function triggerPipeline() {
    setTriggering(true);
    try {
      await apiPost('/admin/pipeline/trigger', { wait_for_completion: false });
      toast.success('Pipeline started in background');
    } catch (e: any) {
      toast.error(e.message);
    }
    setTriggering(false);
  }

  if (loading) return <div className="flex justify-center py-12"><Spinner /></div>;

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-xl text-accent">Dashboard</h1>
        <div className="flex items-center gap-2">
          <Link
            to="/site"
            className="text-xs px-4 py-2 bg-surface-raised border border-text-ghost rounded text-text-muted hover:text-text-primary"
          >
            Site Settings
          </Link>
          <button
            onClick={triggerPipeline}
            disabled={triggering}
            className="text-xs px-4 py-2 bg-accent/20 text-accent rounded hover:bg-accent/30 disabled:opacity-50"
          >
            {triggering ? 'Running pipeline... this can take a few minutes' : 'Trigger Pipeline'}
          </button>
        </div>
      </div>

      {/* Status cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
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

      {operationalHealth && (
        <div className="bg-surface-raised border border-text-ghost rounded p-4 mb-6">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-xs text-text-muted uppercase tracking-wider">Operational Health</h3>
            <span
              className={`text-xs ${
                operationalHealth.status === 'critical'
                  ? 'text-red-400'
                  : operationalHealth.status === 'warn'
                  ? 'text-yellow-300'
                  : 'text-green-400'
              }`}
            >
              {String(operationalHealth.status || 'ok').toUpperCase()}
            </span>
          </div>
          {Array.isArray(operationalHealth.alerts) && operationalHealth.alerts.length > 0 ? (
            <div className="space-y-1">
              {operationalHealth.alerts.slice(0, 4).map((alert: any, idx: number) => (
                <div key={`${alert.code || idx}`} className="text-xs text-text-secondary">
                  <span className={alert.severity === 'critical' ? 'text-red-400' : 'text-yellow-300'}>
                    {String(alert.severity || 'warn').toUpperCase()}
                  </span>
                  <span className="ml-2">{alert.message}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-xs text-green-400">No active operational alerts.</div>
          )}
        </div>
      )}

      {/* LLM Slot Health */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
        {llmSlots.map((slot) => (
          <div key={slot.slot} className="bg-surface-raised border border-text-ghost rounded p-4">
            <div className="flex justify-between items-center mb-2">
              <span className="text-xs text-text-muted uppercase tracking-wider">{slot.slot}</span>
              <span className={`w-2 h-2 rounded-full ${slot.is_active ? 'bg-green-400' : 'bg-text-ghost'}`} />
            </div>
            <div className="text-sm text-text-primary">{inferProvider(slot) || (isSlotConfigured(slot) ? 'Configured' : 'Not configured')}</div>
            <div className="text-xs text-text-muted mt-1">{slot.model_id || '-'}</div>
            {slot.api_key_masked && <div className="text-xs text-green-400 mt-1">Key set ({slot.api_key_masked})</div>}
            {!slot.api_key_masked && slot.is_active && <div className="text-xs text-red-400 mt-1">No API key</div>}
          </div>
        ))}
        {llmSlots.length === 0 && (
          <div className="col-span-full bg-surface-raised border border-text-ghost rounded p-4 text-sm text-text-muted">
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

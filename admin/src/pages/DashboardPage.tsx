import { useState, useEffect } from 'react';
import { apiGet } from '../api/client';

export default function DashboardPage() {
  const [health, setHealth] = useState<any>(null);
  const [pipelineHealth, setPipelineHealth] = useState<any[]>([]);

  useEffect(() => {
    apiGet('/health').then(setHealth).catch(() => {});
    apiGet('/admin/analytics/pipeline-health?days=7').then(setPipelineHealth).catch(() => {});
  }, []);

  return (
    <div>
      <h1 className="text-xl mb-6 text-accent">Dashboard</h1>

      <div className="grid grid-cols-3 gap-4 mb-8">
        <div className="bg-surface-raised border border-text-ghost rounded p-4">
          <div className="text-xs text-text-muted uppercase tracking-wider mb-2">API Status</div>
          <div className={`text-sm ${health?.status === 'ok' ? 'text-green-400' : 'text-red-400'}`}>
            {health?.status || 'checking...'}
          </div>
        </div>

        {pipelineHealth.map((item) => (
          <div key={item.status} className="bg-surface-raised border border-text-ghost rounded p-4">
            <div className="text-xs text-text-muted uppercase tracking-wider mb-2">
              Pipeline: {item.status}
            </div>
            <div className="text-sm text-text-primary">{item.count} runs</div>
          </div>
        ))}
      </div>

      <p className="text-text-muted text-sm">
        Use the sidebar to manage readings, sources, templates, and settings.
      </p>
    </div>
  );
}

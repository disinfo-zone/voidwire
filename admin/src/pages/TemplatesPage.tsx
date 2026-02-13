import { useState, useEffect } from 'react';
import { apiGet } from '../api/client';

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<any[]>([]);

  useEffect(() => {
    apiGet('/admin/templates/').then(setTemplates).catch(() => {});
  }, []);

  return (
    <div>
      <h1 className="text-xl mb-6 text-accent">Prompt Templates</h1>
      <div className="space-y-2">
        {templates.map(t => (
          <div key={t.id} className="bg-surface-raised border border-text-ghost rounded p-4">
            <div className="flex justify-between items-center mb-2">
              <span className="text-sm text-accent">{t.template_name}</span>
              <span className="text-xs text-text-muted">v{t.version}</span>
            </div>
            <pre className="text-xs text-text-secondary overflow-auto max-h-32">{t.content}</pre>
          </div>
        ))}
        {templates.length === 0 && <p className="text-text-muted text-sm">No templates configured.</p>}
      </div>
    </div>
  );
}

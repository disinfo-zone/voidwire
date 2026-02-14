import { useState, useEffect } from 'react';
import { apiGet, apiPost } from '../api/client';
import { useToast } from '../components/ui/ToastProvider';
import ConfirmDialog from '../components/ui/ConfirmDialog';
import Spinner from '../components/ui/Spinner';
import TemplateEditor from '../components/templates/TemplateEditor';

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);
  const [versions, setVersions] = useState<any[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [loading, setLoading] = useState(true);
  const [rollbackId, setRollbackId] = useState<string | null>(null);
  const { toast } = useToast();

  useEffect(() => {
    apiGet('/admin/templates/')
      .then(setTemplates)
      .catch((e: any) => toast.error(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function selectTemplate(t: any) {
    setSelected(t);
    try {
      const v = await apiGet(`/admin/templates/versions/${t.template_name}`);
      setVersions(v);
    } catch { setVersions([]); }
  }

  async function handleCreate(data: any) {
    try {
      await apiPost('/admin/templates/', data);
      setShowCreate(false);
      const ts = await apiGet('/admin/templates/');
      setTemplates(ts);
      toast.success('Template version created');
    } catch (e: any) {
      toast.error(e.message);
    }
  }

  async function confirmRollback() {
    if (!rollbackId) return;
    try {
      await apiPost(`/admin/templates/${rollbackId}/rollback`, {});
      const ts = await apiGet('/admin/templates/');
      setTemplates(ts);
      if (selected) {
        const v = await apiGet(`/admin/templates/versions/${selected.template_name}`);
        setVersions(v);
      }
      toast.success('Rolled back');
    } catch (e: any) {
      toast.error(e.message);
    }
    setRollbackId(null);
  }

  const names = [...new Set(templates.map((t) => t.template_name))];

  if (loading) return <div><h1 className="text-xl mb-6 text-accent">Prompt Templates</h1><div className="flex justify-center py-12"><Spinner /></div></div>;

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-xl text-accent">Prompt Templates</h1>
        <button onClick={() => setShowCreate(!showCreate)} className="text-xs px-3 py-1 bg-surface-raised border border-text-ghost rounded text-accent hover:border-accent">
          + New Version
        </button>
      </div>

      {showCreate && (
        <div className="bg-surface-raised border border-text-ghost rounded p-4 mb-4">
          <TemplateEditor onSave={handleCreate} onCancel={() => setShowCreate(false)} />
        </div>
      )}

      <div className="flex flex-col lg:flex-row gap-4">
        {/* Template list */}
        <div className="w-full lg:w-64 shrink-0 space-y-1">
          {names.map((name) => {
            const active = templates.find((t) => t.template_name === name);
            return (
              <div
                key={name}
                onClick={() => active && selectTemplate(active)}
                className={`bg-surface-raised border rounded p-3 cursor-pointer hover:border-text-muted ${selected?.template_name === name ? 'border-accent' : 'border-text-ghost'}`}
              >
                <div className="text-sm text-accent">{name}</div>
                <div className="text-xs text-text-muted">v{active?.version} (active)</div>
              </div>
            );
          })}
          {names.length === 0 && <p className="text-text-muted text-sm">No templates.</p>}
        </div>

        {/* Detail + versions */}
        {selected && (
          <div className="flex-1 space-y-4">
            <div className="bg-surface-raised border border-text-ghost rounded p-4">
              <div className="flex justify-between items-center mb-2">
                <h3 className="text-sm text-accent">{selected.template_name} v{selected.version}</h3>
                <span className="text-xs text-text-muted">by {selected.author}</span>
              </div>
              <pre className="text-xs text-text-secondary overflow-auto max-h-64 bg-surface rounded p-3">{selected.content}</pre>
              {selected.variables_used?.length > 0 && (
                <div className="mt-2 text-xs text-text-muted">
                  Variables: {selected.variables_used.map((v: string) => <span key={v} className="text-accent ml-1">{`{{${v}}}`}</span>)}
                </div>
              )}
              {selected.tone_parameters && Object.keys(selected.tone_parameters).length > 0 && (
                <div className="mt-2 text-xs text-text-muted">
                  Tone: <span className="text-text-secondary">{JSON.stringify(selected.tone_parameters)}</span>
                </div>
              )}
              {selected.notes && <div className="mt-2 text-xs text-text-muted">Notes: {selected.notes}</div>}
            </div>

            {/* Version history */}
            <div className="bg-surface-raised border border-text-ghost rounded p-4">
              <h4 className="text-xs text-text-muted uppercase tracking-wider mb-2">Version History</h4>
              <div className="space-y-1">
                {versions.map((v) => (
                  <div key={v.id} className="flex justify-between items-center text-xs bg-surface rounded p-2">
                    <div>
                      <span className="text-text-primary">v{v.version}</span>
                      <span className="text-text-muted ml-2">{v.created_at ? new Date(v.created_at).toLocaleDateString() : ''}</span>
                      {v.is_active && <span className="ml-2 text-green-400">active</span>}
                    </div>
                    {!v.is_active && (
                      <button onClick={() => setRollbackId(v.id)} className="text-xs text-accent hover:underline">
                        Rollback
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      <ConfirmDialog
        open={!!rollbackId}
        title="Rollback Template"
        message="Are you sure you want to rollback to this version?"
        onConfirm={confirmRollback}
        onCancel={() => setRollbackId(null)}
      />
    </div>
  );
}

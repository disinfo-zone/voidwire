import { useState, useEffect } from 'react';
import { apiGet, apiPost } from '../api/client';
import { useToast } from '../components/ui/ToastProvider';
import ConfirmDialog from '../components/ui/ConfirmDialog';
import Spinner from '../components/ui/Spinner';
import TemplateEditor from '../components/templates/TemplateEditor';
import { TEMPLATE_VARIABLE_LIBRARY, variableToken } from '../components/templates/templateLibrary';

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);
  const [versions, setVersions] = useState<any[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [loading, setLoading] = useState(true);
  const [rollbackId, setRollbackId] = useState<string | null>(null);
  const { toast } = useToast();

  useEffect(() => {
    async function loadTemplates() {
      try {
        const ts = await apiGet('/admin/templates/');
        setTemplates(ts);
        if (ts.length > 0) {
          await selectTemplate(ts[0]);
        }
      } catch (e: any) {
        toast.error(e.message);
      } finally {
        setLoading(false);
      }
    }
    loadTemplates();
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

      <div className="bg-surface-raised border border-text-ghost rounded p-4 mb-4 space-y-3">
        <h2 className="text-sm text-text-primary">How To Use This Page</h2>
        <p className="text-xs text-text-muted">
          This page is a versioned template library: each new save creates a new version and marks it active.
          Rollback reactivates an older version.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
          <div className="bg-surface border border-text-ghost rounded px-3 py-2">
            <div className="text-text-secondary mb-1">Current Runtime Status</div>
            <div className="text-text-muted">
              Active templates are now used at runtime for synthesis Pass A and Pass B.
              If no matching active template exists, the pipeline falls back to
              <span className="font-mono"> pipeline/src/pipeline/prompts/*.py</span>.
            </div>
          </div>
          <div className="bg-surface border border-text-ghost rounded px-3 py-2">
            <div className="text-text-secondary mb-1">Variables</div>
            <div className="text-text-muted">
              Variables are auto-detected from braces like
              <span className="font-mono"> {'{{date_context}}'} </span>
              and
              <span className="font-mono"> {'{{signals}}'} </span>.
            </div>
          </div>
        </div>
        <div className="text-xs text-text-muted">
          Runtime-resolved template names:
          <span className="text-accent ml-1 font-mono">synthesis_plan</span>,
          <span className="text-accent ml-1 font-mono">synthesis_plan_v1</span>,
          <span className="text-accent ml-1 font-mono">synthesis_prose</span>,
          <span className="text-accent ml-1 font-mono">synthesis_prose_v1</span>,
          <span className="text-accent ml-1 font-mono">starter_synthesis_prose</span>.
        </div>
        <div className="text-xs text-text-muted">
          Safe workflow: create a version, keep notes on intent and changes, compare active version output, then rollback if quality drops.
        </div>
        <div className="bg-surface border border-text-ghost rounded px-3 py-2">
          <div className="text-xs text-text-secondary mb-2">Variable Library</div>
          <div className="flex flex-wrap gap-2">
            {TEMPLATE_VARIABLE_LIBRARY.map((variable) => {
              const token = variableToken(variable.key);
              const tooltip = `${variable.description}\nUsed in: ${variable.usedIn}\nExample: ${variable.example}`;
              return (
                <span
                  key={variable.key}
                  title={tooltip}
                  className="text-[11px] font-mono bg-surface-raised border border-text-ghost rounded px-2 py-1 text-text-secondary"
                >
                  {token}
                </span>
              );
            })}
          </div>
          <div className="text-[11px] text-text-muted mt-2">
            Open
            <span className="mx-1 text-text-secondary">New Version</span>
            to use clickable insert buttons for these variables.
          </div>
        </div>
      </div>

      {showCreate && (
        <div className="bg-surface-raised border border-text-ghost rounded p-4 mb-4">
          <TemplateEditor
            template={selected ?? undefined}
            onSave={handleCreate}
            onCancel={() => setShowCreate(false)}
          />
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

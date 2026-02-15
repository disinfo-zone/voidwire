import { useState, useEffect, useCallback } from 'react';
import { apiGet, apiPut, apiPost } from '../api/client';
import { useToast } from '../components/ui/ToastProvider';
import ConfirmDialog from '../components/ui/ConfirmDialog';
import Spinner from '../components/ui/Spinner';
import SettingField from '../components/settings/SettingField';

const CATEGORIES = ['selection', 'threads', 'synthesis', 'ingestion', 'distillation', 'events'] as const;

const CATEGORY_LABELS: Record<string, string> = {
  selection: 'Selection',
  threads: 'Threads',
  synthesis: 'Synthesis',
  ingestion: 'Ingestion',
  distillation: 'Distillation',
  events: 'Event Readings',
};

function toLabel(key: string): string {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function SettingsPage() {
  const [schema, setSchema] = useState<any>(null);
  const [defaults, setDefaults] = useState<any>(null);
  const [effective, setEffective] = useState<any>(null);
  const [draft, setDraft] = useState<any>(null);
  const [activeTab, setActiveTab] = useState<string>('selection');
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [resetConfirm, setResetConfirm] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    Promise.all([
      apiGet('/admin/settings/schema/pipeline'),
      apiGet('/admin/settings/defaults/pipeline'),
      apiGet('/admin/settings/effective/pipeline'),
    ]).then(([s, d, e]) => {
      setSchema(s);
      setDefaults(d);
      setEffective(e);
      setDraft(JSON.parse(JSON.stringify(e)));
    }).catch((e) => toast.error(e.message));
  }, []);

  const handleChange = useCallback((fieldKey: string, value: any) => {
    setDraft((prev: any) => {
      if (!prev) return prev;
      const next = JSON.parse(JSON.stringify(prev));
      next[activeTab][fieldKey] = value;
      return next;
    });
    setDirty(true);
  }, [activeTab]);

  async function handleSave() {
    if (!draft || !defaults) return;
    setSaving(true);
    try {
      for (const category of CATEGORIES) {
        const catDraft = draft[category];
        const catDefault = defaults[category];
        if (!catDraft || !catDefault) continue;
        for (const [key, val] of Object.entries(catDraft)) {
          if (JSON.stringify(val) !== JSON.stringify(catDefault[key])) {
            await apiPut('/admin/settings/', {
              key: `pipeline.${category}.${key}`,
              value: val,
              category: 'pipeline',
            });
          }
        }
      }
      const e = await apiGet('/admin/settings/effective/pipeline');
      setEffective(e);
      setDraft(JSON.parse(JSON.stringify(e)));
      setDirty(false);
      toast.success('Settings saved');
    } catch (e: any) {
      toast.error(e.message);
    }
    setSaving(false);
  }

  async function handleResetCategory() {
    try {
      await apiPost(`/admin/settings/reset-category/pipeline`, {});
      const e = await apiGet('/admin/settings/effective/pipeline');
      setEffective(e);
      setDraft(JSON.parse(JSON.stringify(e)));
      setDirty(false);
      toast.success('Settings reset to defaults');
    } catch (e: any) {
      toast.error(e.message);
    }
    setResetConfirm(false);
  }

  if (!schema || !defaults || !draft) {
    return (
      <div>
        <h1 className="text-xl mb-6 text-accent">Pipeline Settings</h1>
        <div className="flex justify-center py-12"><Spinner /></div>
      </div>
    );
  }

  const catSchema = schema?.$defs?.[activeTab.charAt(0).toUpperCase() + activeTab.slice(1) + 'Settings'] || {};
  const catProperties = catSchema?.properties || {};
  const catDraft = draft[activeTab] || {};
  const catDefaults = defaults[activeTab] || {};

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-xl text-accent">Pipeline Settings</h1>
        <button
          onClick={() => setResetConfirm(true)}
          className="text-xs px-3 py-1 bg-surface-raised border border-text-ghost rounded text-text-muted hover:text-red-400 hover:border-red-400"
        >
          Reset All to Defaults
        </button>
      </div>

      {/* Category tabs */}
      <div className="flex gap-1 mb-6 border-b border-text-ghost overflow-x-auto">
        {CATEGORIES.map((cat) => (
          <button
            key={cat}
            onClick={() => setActiveTab(cat)}
            className={`px-4 py-2 text-sm border-b-2 -mb-px transition-colors whitespace-nowrap ${
              activeTab === cat
                ? 'border-accent text-accent'
                : 'border-transparent text-text-muted hover:text-text-primary'
            }`}
          >
            {CATEGORY_LABELS[cat]}
          </button>
        ))}
      </div>

      {/* Fields */}
      <div className="space-y-4 bg-surface-raised border border-text-ghost rounded p-4 md:p-6">
        {Object.entries(catProperties).map(([key, fieldSchema]: [string, any]) => (
          <SettingField
            key={`${activeTab}.${key}`}
            label={toLabel(key)}
            fieldKey={key}
            value={catDraft[key]}
            defaultValue={catDefaults[key]}
            schema={fieldSchema}
            onChange={handleChange}
          />
        ))}
        {Object.keys(catProperties).length === 0 && (
          <p className="text-text-muted text-sm">No configurable fields for this category.</p>
        )}
      </div>

      {/* Sticky save bar */}
      {dirty && (
        <div className="fixed bottom-0 left-0 md:left-56 right-0 bg-surface-raised border-t border-text-ghost p-4 flex items-center justify-between">
          <span className="text-sm text-yellow-400">You have unsaved changes</span>
          <div className="flex gap-2">
            <button
              onClick={() => { setDraft(JSON.parse(JSON.stringify(effective))); setDirty(false); }}
              className="px-4 py-2 text-sm text-text-muted hover:text-text-primary"
            >
              Discard
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-4 py-2 text-sm bg-accent/20 text-accent rounded hover:bg-accent/30 disabled:opacity-50"
            >
              {saving ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={resetConfirm}
        title="Reset Settings"
        message="This will reset all pipeline settings to their defaults. This cannot be undone."
        onConfirm={handleResetCategory}
        onCancel={() => setResetConfirm(false)}
        destructive
      />
    </div>
  );
}

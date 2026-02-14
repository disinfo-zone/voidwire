import { useState, useEffect } from 'react';
import { apiGet, apiPut, apiPost } from '../api/client';
import { useToast } from '../components/ui/ToastProvider';
import Spinner from '../components/ui/Spinner';

interface SlotConfig {
  id: string;
  slot: string;
  provider_name: string;
  api_endpoint: string;
  model_id: string;
  api_key_masked: string;
  max_tokens: number | null;
  temperature: number | null;
  extra_params: Record<string, any>;
  is_active: boolean;
}

interface SlotDraft {
  provider_name: string;
  api_endpoint: string;
  model_id: string;
  api_key: string;
  max_tokens: number | null;
  temperature: number;
  extra_params: string;
  is_active: boolean;
}

function SlotPanel({ slot, onRefresh }: { slot: SlotConfig; onRefresh: () => void }) {
  const [draft, setDraft] = useState<SlotDraft>({
    provider_name: slot.provider_name || '',
    api_endpoint: slot.api_endpoint || '',
    model_id: slot.model_id || '',
    api_key: '',
    max_tokens: slot.max_tokens,
    temperature: slot.temperature ?? 0.7,
    extra_params: JSON.stringify(slot.extra_params || {}, null, 2),
    is_active: slot.is_active,
  });
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<any>(null);
  const [saving, setSaving] = useState(false);
  const { toast } = useToast();

  async function handleSave() {
    setSaving(true);
    try {
      const body: any = {
        provider_name: draft.provider_name,
        api_endpoint: draft.api_endpoint,
        model_id: draft.model_id,
        max_tokens: draft.max_tokens,
        temperature: draft.temperature,
        is_active: draft.is_active,
      };
      if (draft.api_key) body.api_key = draft.api_key;
      try { body.extra_params = JSON.parse(draft.extra_params); } catch { body.extra_params = {}; }
      await apiPut(`/admin/llm/${slot.slot}`, body);
      toast.success(`${slot.slot} saved`);
      onRefresh();
    } catch (e: any) {
      toast.error(e.message);
    }
    setSaving(false);
  }

  async function handleTest() {
    setTesting(true);
    setTestResult(null);
    try {
      const result = await apiPost(`/admin/llm/${slot.slot}/test`, {});
      setTestResult(result);
    } catch (err) {
      setTestResult({ status: 'error', error: String(err) });
    }
    setTesting(false);
  }

  return (
    <div className="bg-surface-raised border border-text-ghost rounded p-4 space-y-3">
      <div className="flex justify-between items-center">
        <h3 className="text-sm text-accent font-mono uppercase">{slot.slot}</h3>
        <button
          onClick={() => setDraft({ ...draft, is_active: !draft.is_active })}
          className={`text-xs px-2 py-0.5 rounded ${draft.is_active ? 'bg-green-900 text-green-300' : 'bg-surface text-text-muted'}`}
        >
          {draft.is_active ? 'Active' : 'Inactive'}
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        <div>
          <label className="text-xs text-text-muted">Provider</label>
          <input value={draft.provider_name} onChange={(e) => setDraft({ ...draft, provider_name: e.target.value })} className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary" />
        </div>
        <div>
          <label className="text-xs text-text-muted">Model ID</label>
          <input value={draft.model_id} onChange={(e) => setDraft({ ...draft, model_id: e.target.value })} className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary" />
        </div>
      </div>

      <div>
        <label className="text-xs text-text-muted">API Endpoint</label>
        <input value={draft.api_endpoint} onChange={(e) => setDraft({ ...draft, api_endpoint: e.target.value })} className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary" />
      </div>

      <div>
        <label className="text-xs text-text-muted">
          API Key {slot.api_key_masked && <span className="text-text-ghost ml-1">(current: {slot.api_key_masked})</span>}
        </label>
        <input type="password" value={draft.api_key} onChange={(e) => setDraft({ ...draft, api_key: e.target.value })} placeholder="Leave blank to keep current" className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary" />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        <div>
          <label className="text-xs text-text-muted">Temperature</label>
          <input type="number" step="0.05" min="0" max="2" value={draft.temperature} onChange={(e) => setDraft({ ...draft, temperature: parseFloat(e.target.value) || 0 })} className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary" />
        </div>
        <div>
          <label className="text-xs text-text-muted">Max Tokens</label>
          <input type="number" value={draft.max_tokens ?? ''} onChange={(e) => setDraft({ ...draft, max_tokens: e.target.value ? parseInt(e.target.value) : null })} className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary" />
        </div>
      </div>

      <div>
        <label className="text-xs text-text-muted">Extra Params (JSON)</label>
        <textarea value={draft.extra_params} onChange={(e) => setDraft({ ...draft, extra_params: e.target.value })} rows={2} className="w-full bg-surface border border-text-ghost rounded px-2 py-1 text-xs text-text-primary font-mono" />
      </div>

      <div className="flex gap-2">
        <button onClick={handleSave} disabled={saving} className="text-xs px-3 py-1 bg-accent/20 text-accent rounded hover:bg-accent/30 disabled:opacity-50">
          {saving ? 'Saving...' : 'Save'}
        </button>
        <button onClick={handleTest} disabled={testing} className="text-xs px-3 py-1 bg-surface border border-text-ghost rounded text-text-secondary hover:border-accent disabled:opacity-50">
          {testing ? 'Testing...' : 'Test Connection'}
        </button>
      </div>

      {testResult && (
        <div className={`text-xs p-2 rounded ${testResult.status === 'ok' ? 'bg-green-900/30 text-green-300' : 'bg-red-900/30 text-red-300'}`}>
          {testResult.status === 'ok'
            ? `Connected - ${testResult.latency_ms}ms`
            : `Error: ${testResult.error}`
          }
        </div>
      )}
    </div>
  );
}

export default function LLMConfigPage() {
  const [slots, setSlots] = useState<SlotConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();

  function loadSlots() {
    setLoading(true);
    apiGet('/admin/llm/')
      .then(setSlots)
      .catch((e: any) => toast.error(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => { loadSlots(); }, []);

  if (loading) return <div><h1 className="text-xl mb-6 text-accent">LLM Configuration</h1><div className="flex justify-center py-12"><Spinner /></div></div>;

  return (
    <div>
      <h1 className="text-xl mb-6 text-accent">LLM Configuration</h1>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {slots.map((slot) => (
          <SlotPanel key={slot.slot} slot={slot} onRefresh={loadSlots} />
        ))}
        {slots.length === 0 && (
          <p className="text-text-muted text-sm col-span-full">No LLM slots configured. Complete setup first.</p>
        )}
      </div>
    </div>
  );
}

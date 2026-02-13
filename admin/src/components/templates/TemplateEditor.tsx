import { useState } from 'react';

interface Props {
  template?: any;
  onSave: (data: any) => Promise<void>;
  onCancel: () => void;
}

export default function TemplateEditor({ template, onSave, onCancel }: Props) {
  const [name, setName] = useState(template?.template_name || '');
  const [content, setContent] = useState(template?.content || '');
  const [variables, setVariables] = useState<string[]>(template?.variables_used || []);
  const [toneParams, setToneParams] = useState(JSON.stringify(template?.tone_parameters || {}, null, 2));
  const [notes, setNotes] = useState(template?.notes || '');
  const [saving, setSaving] = useState(false);

  // Highlight {{variable}} patterns
  const detectedVars = [...new Set([...(content.matchAll(/\{\{(\w+)\}\}/g))].map((m) => m[1]))];

  async function handleSave() {
    setSaving(true);
    let tp = {};
    try { tp = JSON.parse(toneParams); } catch {}
    await onSave({
      template_name: name,
      content,
      variables_used: detectedVars.length > 0 ? detectedVars : variables,
      tone_parameters: tp,
      notes: notes || undefined,
    });
    setSaving(false);
  }

  return (
    <div className="space-y-3">
      <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Template name" className="w-full bg-surface border border-text-ghost rounded px-3 py-2 text-sm text-text-primary" />
      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        rows={16}
        className="w-full bg-surface border border-text-ghost rounded px-3 py-2 text-xs text-text-primary font-mono"
      />
      {detectedVars.length > 0 && (
        <div className="text-xs text-text-muted">
          Variables detected: {detectedVars.map((v) => <span key={v} className="text-accent ml-1">{`{{${v}}}`}</span>)}
        </div>
      )}
      <div>
        <label className="text-xs text-text-muted block mb-1">Tone Parameters (JSON)</label>
        <textarea value={toneParams} onChange={(e) => setToneParams(e.target.value)} rows={3} className="w-full bg-surface border border-text-ghost rounded px-3 py-2 text-xs text-text-primary font-mono" />
      </div>
      <div>
        <label className="text-xs text-text-muted block mb-1">Notes</label>
        <input value={notes} onChange={(e) => setNotes(e.target.value)} className="w-full bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary" />
      </div>
      <div className="flex gap-2">
        <button onClick={handleSave} disabled={saving} className="text-xs px-3 py-1 bg-accent/20 text-accent rounded hover:bg-accent/30 disabled:opacity-50">
          {saving ? 'Saving...' : 'Save Version'}
        </button>
        <button onClick={onCancel} className="text-xs px-3 py-1 text-text-muted hover:text-text-primary">Cancel</button>
      </div>
    </div>
  );
}

import { useRef, useState } from 'react';
import {
  STARTER_TEMPLATE_DRAFT,
  TEMPLATE_VARIABLE_LIBRARY,
  variableToken,
} from './templateLibrary';

interface Props {
  template?: any;
  onSave: (data: any) => Promise<void>;
  onCancel: () => void;
}

export default function TemplateEditor({ template, onSave, onCancel }: Props) {
  const initialTemplate = template ?? STARTER_TEMPLATE_DRAFT;
  const [name, setName] = useState<string>(initialTemplate.template_name || '');
  const [content, setContent] = useState<string>(initialTemplate.content || '');
  const variables = template?.variables_used || [];
  const [toneParams, setToneParams] = useState<string>(JSON.stringify(initialTemplate.tone_parameters || {}, null, 2));
  const [notes, setNotes] = useState<string>(initialTemplate.notes || '');
  const [saving, setSaving] = useState(false);
  const contentRef = useRef<HTMLTextAreaElement | null>(null);

  // Highlight {{variable}} patterns
  const detectedVars = [...new Set([...(content.matchAll(/\{\{(\w+)\}\}/g))].map((m) => m[1]))];

  function insertVariable(key: string) {
    const token = variableToken(key);
    const textarea = contentRef.current;
    if (!textarea) {
      setContent((prev) => (prev.endsWith('\n') ? `${prev}${token}` : `${prev}\n${token}`));
      return;
    }

    const start = textarea.selectionStart ?? content.length;
    const end = textarea.selectionEnd ?? content.length;
    const nextValue = `${content.slice(0, start)}${token}${content.slice(end)}`;
    setContent(nextValue);

    const nextCursor = start + token.length;
    requestAnimationFrame(() => {
      textarea.focus();
      textarea.setSelectionRange(nextCursor, nextCursor);
    });
  }

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
      <div>
        <div className="flex items-center justify-between mb-1">
          <label className="text-xs text-text-muted">Variable Library</label>
          <span className="text-[11px] text-text-muted">Click any variable to insert at cursor</span>
        </div>
        <div className="flex flex-wrap gap-2 rounded border border-text-ghost bg-surface px-2 py-2">
          {TEMPLATE_VARIABLE_LIBRARY.map((variable) => {
            const token = variableToken(variable.key);
            const tooltip = `${variable.description}\nUsed in: ${variable.usedIn}\nExample: ${variable.example}`;
            const isUsed = content.includes(token);
            return (
              <button
                key={variable.key}
                type="button"
                onClick={() => insertVariable(variable.key)}
                title={tooltip}
                className={`inline-flex items-center gap-1 rounded border px-2 py-1 text-[11px] font-mono ${
                  isUsed
                    ? 'border-accent bg-accent/20 text-accent'
                    : 'border-text-ghost bg-surface-raised text-text-secondary hover:border-text-muted'
                }`}
              >
                {token}
                <span className="font-sans text-text-muted" title={tooltip}>i</span>
              </button>
            );
          })}
        </div>
      </div>
      <textarea
        ref={contentRef}
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

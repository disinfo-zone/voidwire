import { useState } from 'react';

interface Props {
  label: string;
  value: Record<string, number>;
  defaultValue: Record<string, number>;
  onChange: (v: Record<string, number>) => void;
}

export default function KeyValueField({ label, value, defaultValue, onChange }: Props) {
  const [newKey, setNewKey] = useState('');
  const [newVal, setNewVal] = useState('');
  const isModified = JSON.stringify(value) !== JSON.stringify(defaultValue);

  function addEntry() {
    const k = newKey.trim();
    if (k) {
      onChange({ ...value, [k]: parseFloat(newVal) || 0 });
      setNewKey('');
      setNewVal('');
    }
  }

  function removeEntry(key: string) {
    const next = { ...value };
    delete next[key];
    onChange(next);
  }

  function updateEntry(key: string, val: number) {
    onChange({ ...value, [key]: val });
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <label className="text-sm text-text-secondary w-48 shrink-0">
          {label}
          {isModified && <span className="text-accent ml-1">*</span>}
        </label>
        {isModified && (
          <button onClick={() => onChange(defaultValue)} className="text-xs text-text-muted hover:text-accent">
            reset
          </button>
        )}
      </div>
      <div className="ml-[12.5rem] space-y-1">
        {Object.entries(value).map(([k, v]) => (
          <div key={k} className="flex items-center gap-2">
            <span className="text-xs text-text-primary w-24">{k}</span>
            <input
              type="number"
              step="0.1"
              value={v}
              onChange={(e) => updateEntry(k, parseFloat(e.target.value) || 0)}
              className="w-20 bg-surface border border-text-ghost rounded px-2 py-1 text-xs text-text-primary"
            />
            <button onClick={() => removeEntry(k)} className="text-xs text-red-400 hover:text-red-300">
              remove
            </button>
          </div>
        ))}
        <div className="flex items-center gap-2 mt-2">
          <input
            value={newKey}
            onChange={(e) => setNewKey(e.target.value)}
            placeholder="key"
            className="w-24 bg-surface border border-text-ghost rounded px-2 py-1 text-xs text-text-primary"
          />
          <input
            type="number"
            step="0.1"
            value={newVal}
            onChange={(e) => setNewVal(e.target.value)}
            placeholder="value"
            className="w-20 bg-surface border border-text-ghost rounded px-2 py-1 text-xs text-text-primary"
          />
          <button onClick={addEntry} className="text-xs px-2 py-1 bg-accent/20 text-accent rounded">
            Add
          </button>
        </div>
      </div>
    </div>
  );
}

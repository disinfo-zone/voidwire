import { useState } from 'react';

interface Props {
  label: string;
  value: string[];
  defaultValue: string[];
  onChange: (v: string[]) => void;
}

export default function TagListField({ label, value, defaultValue, onChange }: Props) {
  const [input, setInput] = useState('');
  const isModified = JSON.stringify(value) !== JSON.stringify(defaultValue);

  function addTag() {
    const tag = input.trim();
    if (tag && !value.includes(tag)) {
      onChange([...value, tag]);
      setInput('');
    }
  }

  function removeTag(tag: string) {
    onChange(value.filter((t) => t !== tag));
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <label className="text-sm text-text-secondary w-48 shrink-0">
          {label}
          {isModified && <span className="text-accent ml-1">*</span>}
        </label>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addTag())}
          placeholder="Add item..."
          className="flex-1 bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary"
        />
        <button onClick={addTag} className="text-xs px-2 py-1 bg-accent/20 text-accent rounded">
          Add
        </button>
        {isModified && (
          <button onClick={() => onChange(defaultValue)} className="text-xs text-text-muted hover:text-accent">
            reset
          </button>
        )}
      </div>
      <div className="flex flex-wrap gap-1 ml-[12.5rem]">
        {value.map((tag) => (
          <span
            key={tag}
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-surface-raised border border-text-ghost text-xs text-text-primary"
          >
            {tag}
            <button onClick={() => removeTag(tag)} className="text-text-muted hover:text-red-400">
              x
            </button>
          </span>
        ))}
      </div>
    </div>
  );
}

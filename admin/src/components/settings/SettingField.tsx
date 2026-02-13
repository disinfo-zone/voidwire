import SliderField from './SliderField';
import TagListField from './TagListField';
import KeyValueField from './KeyValueField';

interface Props {
  label: string;
  fieldKey: string;
  value: any;
  defaultValue: any;
  schema?: any;
  onChange: (key: string, value: any) => void;
}

export default function SettingField({ label, fieldKey, value, defaultValue, schema, onChange }: Props) {
  const type = schema?.type;
  const isModified = JSON.stringify(value) !== JSON.stringify(defaultValue);

  // Boolean toggle
  if (type === 'boolean') {
    return (
      <div className="flex items-center gap-4">
        <label className="text-sm text-text-secondary w-48 shrink-0">
          {label}
          {isModified && <span className="text-accent ml-1">*</span>}
        </label>
        <button
          onClick={() => onChange(fieldKey, !value)}
          className={`px-3 py-1 rounded text-xs ${value ? 'bg-green-900 text-green-300' : 'bg-surface border border-text-ghost text-text-muted'}`}
        >
          {value ? 'ON' : 'OFF'}
        </button>
        {isModified && (
          <button onClick={() => onChange(fieldKey, defaultValue)} className="text-xs text-text-muted hover:text-accent">
            reset
          </button>
        )}
      </div>
    );
  }

  // Number (integer or float)
  if (type === 'number' || type === 'integer') {
    const min = schema?.minimum ?? 0;
    const max = schema?.maximum ?? (type === 'integer' ? 100 : 10);
    const step = type === 'integer' ? 1 : 0.01;
    return (
      <SliderField
        label={label}
        value={value ?? defaultValue}
        min={min}
        max={max}
        step={step}
        defaultValue={defaultValue}
        onChange={(v) => onChange(fieldKey, v)}
      />
    );
  }

  // Array of strings
  if (type === 'array' && schema?.items?.type === 'string') {
    return (
      <TagListField
        label={label}
        value={value ?? defaultValue ?? []}
        defaultValue={defaultValue ?? []}
        onChange={(v) => onChange(fieldKey, v)}
      />
    );
  }

  // Array of integers (word ranges)
  if (type === 'array' && schema?.items?.type === 'integer') {
    const arr = value ?? defaultValue ?? [];
    return (
      <div className="flex items-center gap-4">
        <label className="text-sm text-text-secondary w-48 shrink-0">
          {label}
          {isModified && <span className="text-accent ml-1">*</span>}
        </label>
        {arr.map((v: number, i: number) => (
          <input
            key={i}
            type="number"
            value={v}
            onChange={(e) => {
              const next = [...arr];
              next[i] = parseInt(e.target.value) || 0;
              onChange(fieldKey, next);
            }}
            className="w-20 bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary"
          />
        ))}
        {isModified && (
          <button onClick={() => onChange(fieldKey, defaultValue)} className="text-xs text-text-muted hover:text-accent">
            reset
          </button>
        )}
      </div>
    );
  }

  // Object (dict) - key-value pairs
  if (type === 'object') {
    return (
      <KeyValueField
        label={label}
        value={value ?? defaultValue ?? {}}
        defaultValue={defaultValue ?? {}}
        onChange={(v) => onChange(fieldKey, v)}
      />
    );
  }

  // String fallback
  return (
    <div className="flex items-center gap-4">
      <label className="text-sm text-text-secondary w-48 shrink-0">
        {label}
        {isModified && <span className="text-accent ml-1">*</span>}
      </label>
      <input
        type="text"
        value={value ?? ''}
        onChange={(e) => onChange(fieldKey, e.target.value)}
        className="flex-1 bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary"
      />
      {isModified && (
        <button onClick={() => onChange(fieldKey, defaultValue)} className="text-xs text-text-muted hover:text-accent">
          reset
        </button>
      )}
    </div>
  );
}

import { useState } from 'react';

interface Props {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  defaultValue: number;
  onChange: (v: number) => void;
}

export default function SliderField({ label, value, min, max, step, defaultValue, onChange }: Props) {
  const isModified = value !== defaultValue;
  return (
    <div className="flex items-center gap-4">
      <label className="text-sm text-text-secondary w-48 shrink-0">
        {label}
        {isModified && <span className="text-accent ml-1">*</span>}
      </label>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="flex-1 accent-accent"
      />
      <input
        type="number"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
        className="w-20 bg-surface border border-text-ghost rounded px-2 py-1 text-sm text-text-primary text-right"
      />
      {isModified && (
        <button onClick={() => onChange(defaultValue)} className="text-xs text-text-muted hover:text-accent" title="Reset">
          reset
        </button>
      )}
    </div>
  );
}

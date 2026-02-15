import { useEffect, useState } from 'react';

interface Props {
  reading: any;
  onSave: (data: any) => Promise<void>;
}

export default function ReadingEditor({ reading, onSave }: Props) {
  const standard = reading.published_standard || reading.generated_standard || {};
  const extended = reading.published_extended || reading.generated_extended || {};
  const annotationsSource = reading.published_annotations || reading.generated_annotations || [];

  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [extTitle, setExtTitle] = useState('');
  const [extSubtitle, setExtSubtitle] = useState('');
  const [sections, setSections] = useState<any[]>([]);
  const [annotations, setAnnotations] = useState<any[]>([]);
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setTitle(standard.title || '');
    setBody(standard.body || '');
    setExtTitle(extended.title || '');
    setExtSubtitle(extended.subtitle || '');
    setSections(Array.isArray(extended.sections) ? extended.sections : []);
    setAnnotations(Array.isArray(annotationsSource) ? annotationsSource : []);
    setNotes(reading.editorial_notes || '');
  }, [reading]); // eslint-disable-line react-hooks/exhaustive-deps

  function countWords(text: string): number {
    return text.split(/\s+/).filter(Boolean).length;
  }

  function updateSection(index: number, patch: Record<string, unknown>) {
    setSections((prev) => prev.map((sec, i) => (i === index ? { ...sec, ...patch } : sec)));
  }

  function removeSection(index: number) {
    setSections((prev) => prev.filter((_, i) => i !== index));
  }

  function addSection() {
    setSections((prev) => [...prev, { heading: '', body: '' }]);
  }

  function updateAnnotation(index: number, patch: Record<string, unknown>) {
    setAnnotations((prev) => prev.map((ann, i) => (i === index ? { ...ann, ...patch } : ann)));
  }

  function removeAnnotation(index: number) {
    setAnnotations((prev) => prev.filter((_, i) => i !== index));
  }

  function addAnnotation() {
    setAnnotations((prev) => [...prev, { aspect: '', gloss: '', cultural_resonance: '', temporal_arc: '' }]);
  }

  async function handleSave() {
    setSaving(true);
    try {
      const normalizedSections = sections.map((sec) => ({
        heading: sec?.heading || '',
        body: sec?.body || '',
      }));
      const normalizedAnnotations = annotations.map((ann) => ({
        aspect: ann?.aspect || '',
        gloss: ann?.gloss || '',
        cultural_resonance: ann?.cultural_resonance || '',
        temporal_arc: ann?.temporal_arc || '',
      }));

      await onSave({
        published_standard: { title, body, word_count: countWords(body) },
        published_extended: {
          title: extTitle,
          subtitle: extSubtitle,
          sections: normalizedSections,
          word_count: normalizedSections.reduce((acc: number, s: any) => acc + countWords(s.body || ''), 0),
        },
        published_annotations: normalizedAnnotations,
        editorial_notes: notes,
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-xs text-text-muted uppercase tracking-wider mb-2">Standard Reading</h3>
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Title"
          className="w-full bg-surface border border-text-ghost rounded px-3 py-2 text-sm text-text-primary mb-2"
        />
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={12}
          className="w-full bg-surface border border-text-ghost rounded px-3 py-2 text-sm text-text-primary font-serif"
        />
        <div className="text-xs text-text-muted mt-1">{countWords(body)} words</div>
      </div>

      <div>
        <h3 className="text-xs text-text-muted uppercase tracking-wider mb-2">Extended Reading</h3>
        <div className="grid grid-cols-2 gap-2 mb-2">
          <input value={extTitle} onChange={(e) => setExtTitle(e.target.value)} placeholder="Title" className="bg-surface border border-text-ghost rounded px-3 py-2 text-sm text-text-primary" />
          <input value={extSubtitle} onChange={(e) => setExtSubtitle(e.target.value)} placeholder="Subtitle" className="bg-surface border border-text-ghost rounded px-3 py-2 text-sm text-text-primary" />
        </div>
        {sections.map((sec: any, i: number) => (
          <div key={i} className="mb-3 border border-text-ghost rounded p-2">
            <input
              value={sec.heading || ''}
              onChange={(e) => updateSection(i, { heading: e.target.value })}
              placeholder="Section heading"
              className="w-full bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary mb-1"
            />
            <textarea
              value={sec.body || ''}
              onChange={(e) => updateSection(i, { body: e.target.value })}
              rows={6}
              className="w-full bg-surface border border-text-ghost rounded px-3 py-2 text-xs text-text-primary font-serif"
            />
            <div className="flex justify-between mt-1">
              <span className="text-[11px] text-text-muted">{countWords(sec.body || '')} words</span>
              <button
                type="button"
                onClick={() => removeSection(i)}
                className="text-[11px] text-red-300 hover:text-red-200"
              >
                Remove section
              </button>
            </div>
          </div>
        ))}
        <button type="button" onClick={addSection} className="text-xs px-2 py-1 bg-surface border border-text-ghost rounded text-text-secondary hover:border-text-muted">
          + Add Section
        </button>
      </div>

      <div>
        <h3 className="text-xs text-text-muted uppercase tracking-wider mb-2">Transit Annotations</h3>
        {annotations.map((ann: any, i: number) => (
          <div key={i} className="mb-3 border border-text-ghost rounded p-2 space-y-1">
            <input
              value={ann.aspect || ''}
              onChange={(e) => updateAnnotation(i, { aspect: e.target.value })}
              placeholder="Aspect"
              className="w-full bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary"
            />
            <textarea
              value={ann.gloss || ''}
              onChange={(e) => updateAnnotation(i, { gloss: e.target.value })}
              placeholder="Gloss"
              rows={2}
              className="w-full bg-surface border border-text-ghost rounded px-3 py-2 text-xs text-text-primary"
            />
            <textarea
              value={ann.cultural_resonance || ''}
              onChange={(e) => updateAnnotation(i, { cultural_resonance: e.target.value })}
              placeholder="Cultural resonance"
              rows={2}
              className="w-full bg-surface border border-text-ghost rounded px-3 py-2 text-xs text-text-primary"
            />
            <textarea
              value={ann.temporal_arc || ''}
              onChange={(e) => updateAnnotation(i, { temporal_arc: e.target.value })}
              placeholder="Temporal arc"
              rows={2}
              className="w-full bg-surface border border-text-ghost rounded px-3 py-2 text-xs text-text-primary"
            />
            <div className="flex justify-end">
              <button
                type="button"
                onClick={() => removeAnnotation(i)}
                className="text-[11px] text-red-300 hover:text-red-200"
              >
                Remove annotation
              </button>
            </div>
          </div>
        ))}
        <button type="button" onClick={addAnnotation} className="text-xs px-2 py-1 bg-surface border border-text-ghost rounded text-text-secondary hover:border-text-muted">
          + Add Annotation
        </button>
      </div>

      <div>
        <h3 className="text-xs text-text-muted uppercase tracking-wider mb-2">Editorial Notes</h3>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={3}
          placeholder="Notes about editorial changes..."
          className="w-full bg-surface border border-text-ghost rounded px-3 py-2 text-sm text-text-primary"
        />
      </div>

      <button
        onClick={handleSave}
        disabled={saving}
        className="px-4 py-2 text-sm bg-accent/20 text-accent rounded hover:bg-accent/30 disabled:opacity-50"
      >
        {saving ? 'Saving...' : 'Save Content'}
      </button>
    </div>
  );
}

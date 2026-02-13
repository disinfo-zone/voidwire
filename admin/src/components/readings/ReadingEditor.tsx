import { useState } from 'react';

interface Props {
  reading: any;
  onSave: (data: any) => Promise<void>;
}

export default function ReadingEditor({ reading, onSave }: Props) {
  const standard = reading.published_standard || reading.generated_standard || {};
  const extended = reading.published_extended || reading.generated_extended || {};

  const [title, setTitle] = useState(standard.title || '');
  const [body, setBody] = useState(standard.body || '');
  const [extTitle, setExtTitle] = useState(extended.title || '');
  const [extSubtitle, setExtSubtitle] = useState(extended.subtitle || '');
  const [sections, setSections] = useState<any[]>(extended.sections || []);
  const [notes, setNotes] = useState(reading.editorial_notes || '');
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    setSaving(true);
    await onSave({
      published_standard: { title, body, word_count: body.split(/\s+/).length },
      published_extended: { title: extTitle, subtitle: extSubtitle, sections, word_count: sections.reduce((acc: number, s: any) => acc + (s.body?.split(/\s+/).length || 0), 0) },
      editorial_notes: notes,
    });
    setSaving(false);
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
        <div className="text-xs text-text-muted mt-1">{body.split(/\s+/).filter(Boolean).length} words</div>
      </div>

      <div>
        <h3 className="text-xs text-text-muted uppercase tracking-wider mb-2">Extended Reading</h3>
        <div className="grid grid-cols-2 gap-2 mb-2">
          <input value={extTitle} onChange={(e) => setExtTitle(e.target.value)} placeholder="Title" className="bg-surface border border-text-ghost rounded px-3 py-2 text-sm text-text-primary" />
          <input value={extSubtitle} onChange={(e) => setExtSubtitle(e.target.value)} placeholder="Subtitle" className="bg-surface border border-text-ghost rounded px-3 py-2 text-sm text-text-primary" />
        </div>
        {sections.map((sec: any, i: number) => (
          <div key={i} className="mb-3">
            <input
              value={sec.heading || ''}
              onChange={(e) => { const next = [...sections]; next[i] = { ...sec, heading: e.target.value }; setSections(next); }}
              placeholder="Section heading"
              className="w-full bg-surface border border-text-ghost rounded px-3 py-1 text-sm text-text-primary mb-1"
            />
            <textarea
              value={sec.body || ''}
              onChange={(e) => { const next = [...sections]; next[i] = { ...sec, body: e.target.value }; setSections(next); }}
              rows={6}
              className="w-full bg-surface border border-text-ghost rounded px-3 py-2 text-xs text-text-primary font-serif"
            />
          </div>
        ))}
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

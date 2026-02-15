import { useEffect, useMemo, useState } from 'react';
import { apiGet, apiPut } from '../api/client';
import { useToast } from '../components/ui/ToastProvider';
import Spinner from '../components/ui/Spinner';

type ContentSection = {
  heading: string;
  body: string;
};

type ContentPagePayload = {
  slug: string;
  title: string;
  sections: ContentSection[];
  updated_at?: string | null;
};

type ContentPageSummary = {
  slug: string;
  title: string;
  sections_count: number;
  updated_at?: string | null;
};

function clonePage(page: ContentPagePayload): ContentPagePayload {
  return {
    slug: page.slug,
    title: page.title,
    updated_at: page.updated_at ?? null,
    sections: page.sections.map((section) => ({
      heading: section.heading ?? '',
      body: section.body ?? '',
    })),
  };
}

export default function ContentPage() {
  const [pages, setPages] = useState<ContentPageSummary[]>([]);
  const [selectedSlug, setSelectedSlug] = useState('');
  const [page, setPage] = useState<ContentPagePayload | null>(null);
  const [draft, setDraft] = useState<ContentPagePayload | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingPage, setLoadingPage] = useState(false);
  const [saving, setSaving] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    void loadPages();
  }, []);

  useEffect(() => {
    if (!selectedSlug) return;
    void loadPage(selectedSlug);
  }, [selectedSlug]);

  async function loadPages(preferredSlug?: string) {
    setLoadingList(true);
    try {
      const list = await apiGet('/admin/content/pages') as ContentPageSummary[];
      setPages(list);
      setSelectedSlug((current) => {
        const target = preferredSlug || current;
        if (target && list.some((item) => item.slug === target)) return target;
        return list[0]?.slug || '';
      });
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : 'Failed to load pages';
      toast.error(message);
    } finally {
      setLoadingList(false);
    }
  }

  async function loadPage(slug: string) {
    setLoadingPage(true);
    try {
      const data = await apiGet(`/admin/content/pages/${encodeURIComponent(slug)}`) as ContentPagePayload;
      const normalized = clonePage(data);
      setPage(normalized);
      setDraft(clonePage(normalized));
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : 'Failed to load page';
      toast.error(message);
    } finally {
      setLoadingPage(false);
    }
  }

  function updateTitle(value: string) {
    setDraft((prev) => (prev ? { ...prev, title: value } : prev));
  }

  function updateSection(index: number, key: 'heading' | 'body', value: string) {
    setDraft((prev) => {
      if (!prev) return prev;
      const sections = prev.sections.map((section, sectionIndex) =>
        sectionIndex === index ? { ...section, [key]: value } : section,
      );
      return { ...prev, sections };
    });
  }

  function addSection() {
    setDraft((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        sections: [...prev.sections, { heading: '', body: '' }],
      };
    });
  }

  function removeSection(index: number) {
    setDraft((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        sections: prev.sections.filter((_, sectionIndex) => sectionIndex !== index),
      };
    });
  }

  async function savePage() {
    if (!draft) return;
    setSaving(true);
    try {
      const payload = {
        title: draft.title,
        sections: draft.sections,
      };
      const saved = await apiPut(`/admin/content/pages/${encodeURIComponent(draft.slug)}`, payload) as ContentPagePayload;
      const normalized = clonePage(saved);
      setPage(normalized);
      setDraft(clonePage(normalized));
      setPages((prev) =>
        prev.map((item) =>
          item.slug === normalized.slug
            ? {
                ...item,
                title: normalized.title,
                sections_count: normalized.sections.length,
                updated_at: normalized.updated_at ?? null,
              }
            : item,
        ),
      );
      toast.success('Content page saved');
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : 'Failed to save page';
      toast.error(message);
    } finally {
      setSaving(false);
    }
  }

  const isDirty = useMemo(() => {
    if (!page || !draft) return false;
    return JSON.stringify({ title: page.title, sections: page.sections }) !== JSON.stringify({ title: draft.title, sections: draft.sections });
  }, [page, draft]);

  if (loadingList) {
    return (
      <div>
        <h1 className="text-xl text-accent mb-6">Content</h1>
        <div className="flex justify-center py-12"><Spinner /></div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-xl text-accent">Content</h1>
        <div className="flex gap-2">
          <button
            onClick={addSection}
            disabled={!draft}
            className="text-xs px-3 py-1 bg-surface-raised border border-text-ghost rounded text-text-muted hover:text-text-primary disabled:opacity-50"
          >
            Add Section
          </button>
          <button
            onClick={savePage}
            disabled={!draft || !isDirty || saving}
            className="text-xs px-3 py-1 bg-accent/20 text-accent rounded hover:bg-accent/30 disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>

      <div className="flex flex-col lg:flex-row gap-4">
        <div className="w-full lg:w-72 shrink-0 space-y-2">
          {pages.map((item) => (
            <button
              key={item.slug}
              onClick={() => setSelectedSlug(item.slug)}
              className={`w-full text-left bg-surface-raised border rounded p-3 ${
                selectedSlug === item.slug ? 'border-accent' : 'border-text-ghost hover:border-text-muted'
              }`}
            >
              <div className="text-sm text-text-primary">{item.title || item.slug}</div>
              <div className="text-xs text-text-muted mt-1">/{item.slug} • {item.sections_count} sections</div>
            </button>
          ))}
          {pages.length === 0 && <div className="text-sm text-text-muted">No editable pages configured.</div>}
        </div>

        <div className="flex-1 bg-surface-raised border border-text-ghost rounded p-4 space-y-4">
          {loadingPage && (
            <div className="flex justify-center py-8"><Spinner /></div>
          )}

          {!loadingPage && draft && (
            <>
              <div>
                <label className="text-xs text-text-muted block mb-1">Page Title</label>
                <input
                  value={draft.title}
                  onChange={(e) => updateTitle(e.target.value)}
                  className="w-full bg-surface border border-text-ghost rounded px-3 py-2 text-sm text-text-primary"
                />
              </div>

              <div className="space-y-3">
                {draft.sections.map((section, index) => (
                  <div key={index} className="bg-surface border border-text-ghost rounded p-3 space-y-2">
                    <div className="flex justify-between items-center">
                      <div className="text-xs text-text-muted uppercase tracking-wider">Section {index + 1}</div>
                      <button
                        onClick={() => removeSection(index)}
                        className="text-[11px] text-red-300 hover:text-red-200"
                      >
                        Remove
                      </button>
                    </div>
                    <input
                      value={section.heading}
                      onChange={(e) => updateSection(index, 'heading', e.target.value)}
                      placeholder="Heading"
                      className="w-full bg-surface-raised border border-text-ghost rounded px-2 py-1 text-sm text-text-primary"
                    />
                    <textarea
                      value={section.body}
                      onChange={(e) => updateSection(index, 'body', e.target.value)}
                      placeholder="Section body"
                      rows={8}
                      className="w-full bg-surface-raised border border-text-ghost rounded px-2 py-2 text-sm text-text-primary"
                    />
                  </div>
                ))}
              </div>
            </>
          )}

          {!loadingPage && !draft && (
            <div className="text-sm text-text-muted">Select a content page to edit.</div>
          )}
        </div>
      </div>
    </div>
  );
}


import type { APIRoute } from 'astro';

const SITE_URL = 'https://voidwire.net';
const API_URL = process.env.API_URL || import.meta.env.API_URL || 'http://voidwire-api:8000';

function escapeXml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

export const GET: APIRoute = async () => {
  let items: Array<{ date_context: string; title: string; body?: string }> = [];

  try {
    const res = await fetch(`${API_URL}/v1/archive?per_page=20`);
    if (res.ok) {
      const data = await res.json();
      items = data.items || data;
    }
  } catch {
    // Return empty feed on error
  }

  const updatedAt = items.length > 0
    ? new Date(items[0].date_context).toISOString()
    : new Date().toISOString();

  const entriesXml = items
    .map((item) => {
      const link = `${SITE_URL}/reading/${item.date_context}`;
      const published = new Date(item.date_context).toISOString();
      const summary = item.body
        ? escapeXml(item.body.substring(0, 500) + (item.body.length > 500 ? '...' : ''))
        : '';
      return `  <entry>
    <title>${escapeXml(item.title)}</title>
    <link href="${link}" rel="alternate" type="text/html" />
    <id>${link}</id>
    <published>${published}</published>
    <updated>${published}</updated>
    <summary type="text">${summary}</summary>
  </entry>`;
    })
    .join('\n');

  const atom = `<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>VOIDWIRE</title>
  <subtitle>Daily transmissions from the celestial wire.</subtitle>
  <link href="${SITE_URL}" rel="alternate" type="text/html" />
  <link href="${SITE_URL}/feed.atom" rel="self" type="application/atom+xml" />
  <id>${SITE_URL}/</id>
  <updated>${updatedAt}</updated>
  <author>
    <name>VOIDWIRE</name>
  </author>
${entriesXml}
</feed>`;

  return new Response(atom, {
    status: 200,
    headers: {
      'Content-Type': 'application/atom+xml; charset=utf-8',
      'Cache-Control': 'public, max-age=3600',
    },
  });
};

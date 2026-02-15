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

  const itemsXml = items
    .map((item) => {
      const link = `${SITE_URL}/reading/${item.date_context}`;
      const description = item.body
        ? escapeXml(item.body.substring(0, 500) + (item.body.length > 500 ? '...' : ''))
        : '';
      return `    <item>
      <title>${escapeXml(item.title)}</title>
      <link>${link}</link>
      <guid isPermaLink="true">${link}</guid>
      <pubDate>${new Date(item.date_context).toUTCString()}</pubDate>
      <description>${description}</description>
    </item>`;
    })
    .join('\n');

  const rss = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>VOIDWIRE</title>
    <link>${SITE_URL}</link>
    <description>Daily transmissions from the celestial wire.</description>
    <language>en-us</language>
    <atom:link href="${SITE_URL}/feed.xml" rel="self" type="application/rss+xml" />
    <lastBuildDate>${new Date().toUTCString()}</lastBuildDate>
${itemsXml}
  </channel>
</rss>`;

  return new Response(rss, {
    status: 200,
    headers: {
      'Content-Type': 'application/rss+xml; charset=utf-8',
      'Cache-Control': 'public, max-age=3600',
    },
  });
};

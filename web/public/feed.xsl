<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:atom="http://www.w3.org/2005/Atom"
  exclude-result-prefixes="atom">

  <xsl:output method="html" encoding="UTF-8" indent="yes" />

  <!-- RSS 2.0 -->
  <xsl:template match="/rss">
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>VOIDWIRE — RSS Feed</title>
        <xsl:call-template name="styles" />
      </head>
      <body>
        <div class="feed-page">
          <header class="feed-header">
            <div class="feed-badge">RSS FEED</div>
            <h1><a href="{channel/link}">VOIDWIRE</a></h1>
            <p class="feed-tagline"><xsl:value-of select="channel/description" /></p>
            <p class="feed-subscribe">
              Subscribe by copying this URL into your feed reader:
              <code><xsl:value-of select="channel/atom:link[@rel='self']/@href" /></code>
            </p>
          </header>
          <main class="feed-list">
            <xsl:for-each select="channel/item">
              <article class="feed-item">
                <a href="{link}">
                  <div class="item-title"><xsl:value-of select="title" /></div>
                  <div class="item-date"><xsl:value-of select="pubDate" /></div>
                  <xsl:if test="description != ''">
                    <div class="item-summary"><xsl:value-of select="description" /></div>
                  </xsl:if>
                </a>
              </article>
            </xsl:for-each>
          </main>
        </div>
      </body>
    </html>
  </xsl:template>

  <!-- Atom 1.0 -->
  <xsl:template match="/atom:feed">
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>VOIDWIRE — Atom Feed</title>
        <xsl:call-template name="styles" />
      </head>
      <body>
        <div class="feed-page">
          <header class="feed-header">
            <div class="feed-badge">ATOM FEED</div>
            <h1><a href="{atom:link[@rel='alternate']/@href}">VOIDWIRE</a></h1>
            <p class="feed-tagline"><xsl:value-of select="atom:subtitle" /></p>
            <p class="feed-subscribe">
              Subscribe by copying this URL into your feed reader:
              <code><xsl:value-of select="atom:link[@rel='self']/@href" /></code>
            </p>
          </header>
          <main class="feed-list">
            <xsl:for-each select="atom:entry">
              <article class="feed-item">
                <a href="{atom:link[@rel='alternate']/@href}">
                  <div class="item-title"><xsl:value-of select="atom:title" /></div>
                  <div class="item-date"><xsl:value-of select="atom:published" /></div>
                  <xsl:if test="atom:summary != ''">
                    <div class="item-summary"><xsl:value-of select="atom:summary" /></div>
                  </xsl:if>
                </a>
              </article>
            </xsl:for-each>
          </main>
        </div>
      </body>
    </html>
  </xsl:template>

  <xsl:template name="styles">
    <style>
      *, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }

      @import url('https://fonts.googleapis.com/css2?family=EB+Garamond:wght@400;500&amp;family=Inter:wght@300;400;500&amp;family=JetBrains+Mono:wght@300;400&amp;display=swap');

      body {
        background: linear-gradient(180deg, #060a16 0%, #050914 48%, #04070f 100%);
        color: #d9d4c9;
        font-family: 'EB Garamond', Georgia, serif;
        line-height: 1.85;
        min-height: 100vh;
        -webkit-font-smoothing: antialiased;
      }

      a { color: #d6af72; text-decoration: none; }
      a:hover { opacity: 0.7; }

      .feed-page {
        max-width: 680px;
        margin: 0 auto;
        padding: 2rem 1.5rem 4rem;
      }

      .feed-header {
        text-align: center;
        margin-bottom: 3rem;
        padding-bottom: 2rem;
        border-bottom: 1px solid #252a30;
      }

      .feed-badge {
        font-family: 'Inter', system-ui, sans-serif;
        font-size: 0.55rem;
        font-weight: 500;
        letter-spacing: 0.35em;
        color: #d6af72;
        border: 1px solid rgba(214, 175, 114, 0.25);
        display: inline-block;
        padding: 0.35rem 1rem;
        margin-bottom: 1.5rem;
        border-radius: 2px;
      }

      .feed-header h1 {
        font-family: 'Inter', system-ui, sans-serif;
        font-size: 0.9rem;
        font-weight: 500;
        letter-spacing: 0.3em;
        margin-bottom: 0.75rem;
      }

      .feed-tagline {
        color: #6f6a62;
        font-size: 1.05rem;
        margin-bottom: 1.5rem;
      }

      .feed-subscribe {
        font-family: 'Inter', system-ui, sans-serif;
        font-size: 0.72rem;
        color: #6f6a62;
        line-height: 1.6;
      }

      .feed-subscribe code {
        display: block;
        margin-top: 0.5rem;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.65rem;
        color: #a9a39a;
        background: rgba(255, 255, 255, 0.04);
        border: 1px solid #252a30;
        padding: 0.5rem 0.75rem;
        border-radius: 3px;
        word-break: break-all;
      }

      .feed-list {
        display: flex;
        flex-direction: column;
      }

      .feed-item {
        border-bottom: 1px solid #252a30;
      }

      .feed-item a {
        display: block;
        padding: 1.25rem 0;
        color: inherit;
        transition: opacity 0.3s ease;
      }

      .feed-item a:hover { opacity: 1; }
      .feed-item a:hover .item-title { color: #d6af72; }

      .item-title {
        font-size: 1.15rem;
        color: #a9a39a;
        margin-bottom: 0.35rem;
        transition: color 0.3s ease;
      }

      .item-date {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.65rem;
        color: #6f6a62;
        letter-spacing: 0.1em;
      }

      .item-summary {
        margin-top: 0.6rem;
        font-size: 0.95rem;
        color: #6f6a62;
        line-height: 1.7;
      }

      @media (max-width: 768px) {
        .feed-page { padding: 1.5rem 1rem 3rem; }
        .item-title { font-size: 1.05rem; }
      }
    </style>
  </xsl:template>

</xsl:stylesheet>

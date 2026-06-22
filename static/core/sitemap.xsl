<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0"
                xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:sitemap="http://www.sitemaps.org/schemas/sitemap/0.9"
                xmlns:xhtml="http://www.w3.org/1999/xhtml"
                xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">
    <xsl:output method="html" encoding="UTF-8" indent="yes" />

    <xsl:template match="/">
        <html lang="en">
            <head>
                <meta charset="UTF-8" />
                <meta name="viewport" content="width=device-width, initial-scale=1" />
                <title>Undersun Estate Sitemap</title>
                <style>
                    :root {
                        color-scheme: light;
                        --primary: #18233f;
                        --muted: #667085;
                        --line: #e6e8ee;
                        --bg: #f7f8fb;
                        --accent: #f1b400;
                    }

                    * {
                        box-sizing: border-box;
                    }

                    body {
                        margin: 0;
                        background: var(--bg);
                        color: var(--primary);
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                        font-size: 14px;
                        line-height: 1.5;
                    }

                    main {
                        max-width: 1180px;
                        margin: 0 auto;
                        padding: 32px 18px 48px;
                    }

                    .hero {
                        margin-bottom: 22px;
                    }

                    .eyebrow {
                        margin: 0 0 8px;
                        color: var(--accent);
                        font-size: 12px;
                        font-weight: 700;
                        letter-spacing: .16em;
                        text-transform: uppercase;
                    }

                    h1 {
                        margin: 0;
                        font-size: clamp(28px, 4vw, 42px);
                        line-height: 1.1;
                    }

                    .summary {
                        display: flex;
                        flex-wrap: wrap;
                        gap: 10px;
                        margin-top: 16px;
                    }

                    .pill {
                        display: inline-flex;
                        align-items: center;
                        min-height: 34px;
                        border: 1px solid var(--line);
                        border-radius: 999px;
                        background: #fff;
                        padding: 7px 12px;
                        color: var(--muted);
                        font-weight: 600;
                    }

                    table {
                        width: 100%;
                        border-collapse: collapse;
                        overflow: hidden;
                        border: 1px solid var(--line);
                        border-radius: 8px;
                        background: #fff;
                        box-shadow: 0 14px 30px rgba(24, 35, 63, .05);
                    }

                    th,
                    td {
                        border-bottom: 1px solid var(--line);
                        padding: 12px 14px;
                        text-align: left;
                        vertical-align: top;
                    }

                    th {
                        background: #f1f3f7;
                        color: var(--muted);
                        font-size: 12px;
                        font-weight: 800;
                        letter-spacing: .08em;
                        text-transform: uppercase;
                    }

                    tr:last-child td {
                        border-bottom: 0;
                    }

                    a {
                        color: #1a4f9c;
                        text-decoration: none;
                        overflow-wrap: anywhere;
                    }

                    a:hover {
                        text-decoration: underline;
                    }

                    .muted {
                        color: var(--muted);
                    }

                    .alternates {
                        display: flex;
                        flex-direction: column;
                        gap: 5px;
                    }

                    .images {
                        display: flex;
                        flex-direction: column;
                        gap: 10px;
                    }

                    .image-item {
                        display: flex;
                        flex-direction: column;
                        gap: 2px;
                    }

                    .alternate {
                        display: grid;
                        grid-template-columns: 72px minmax(0, 1fr);
                        gap: 8px;
                    }

                    .lang {
                        color: var(--muted);
                        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
                        font-size: 12px;
                        font-weight: 700;
                    }

                    @media (max-width: 760px) {
                        main {
                            padding: 24px 12px 36px;
                        }

                        table,
                        thead,
                        tbody,
                        th,
                        td,
                        tr {
                            display: block;
                        }

                        thead {
                            display: none;
                        }

                        tr {
                            border-bottom: 1px solid var(--line);
                            padding: 12px;
                        }

                        tr:last-child {
                            border-bottom: 0;
                        }

                        td {
                            border: 0;
                            padding: 5px 0;
                        }

                        td::before {
                            display: block;
                            margin-bottom: 2px;
                            color: var(--muted);
                            font-size: 11px;
                            font-weight: 800;
                            letter-spacing: .08em;
                            text-transform: uppercase;
                        }

                        td[data-label="URL"]::before {
                            content: "URL";
                        }

                        td[data-label="Last modified"]::before {
                            content: "Last modified";
                        }

                        td[data-label="Alternates"]::before {
                            content: "Alternates";
                        }

                        td[data-label="Images"]::before {
                            content: "Images";
                        }
                    }
                </style>
            </head>
            <body>
                <main>
                    <xsl:choose>
                        <xsl:when test="sitemap:sitemapindex">
                            <section class="hero">
                                <p class="eyebrow">Sitemap Index</p>
                                <h1>Undersun Estate sitemap</h1>
                                <div class="summary">
                                    <span class="pill">
                                        <xsl:value-of select="count(sitemap:sitemapindex/sitemap:sitemap)" />
                                        <xsl:text> sitemap files</xsl:text>
                                    </span>
                                    <span class="pill">XML source for search engines</span>
                                </div>
                            </section>
                            <table>
                                <thead>
                                    <tr>
                                        <th>Sitemap</th>
                                        <th>Last modified</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <xsl:for-each select="sitemap:sitemapindex/sitemap:sitemap">
                                        <tr>
                                            <td data-label="URL">
                                                <a href="{sitemap:loc}">
                                                    <xsl:value-of select="sitemap:loc" />
                                                </a>
                                            </td>
                                            <td data-label="Last modified">
                                                <xsl:choose>
                                                    <xsl:when test="sitemap:lastmod">
                                                        <xsl:value-of select="sitemap:lastmod" />
                                                    </xsl:when>
                                                    <xsl:otherwise>
                                                        <span class="muted">Not specified</span>
                                                    </xsl:otherwise>
                                                </xsl:choose>
                                            </td>
                                        </tr>
                                    </xsl:for-each>
                                </tbody>
                            </table>
                        </xsl:when>
                        <xsl:otherwise>
                            <section class="hero">
                                <p class="eyebrow">URL Sitemap</p>
                                <h1>Undersun Estate URLs</h1>
                                <div class="summary">
                                    <span class="pill">
                                        <xsl:value-of select="count(sitemap:urlset/sitemap:url)" />
                                        <xsl:text> URLs</xsl:text>
                                    </span>
                                    <span class="pill">Includes hreflang alternates</span>
                                    <xsl:if test="count(sitemap:urlset/sitemap:url/image:image) &gt; 0">
                                        <span class="pill">
                                            <xsl:value-of select="count(sitemap:urlset/sitemap:url/image:image)" />
                                            <xsl:text> images</xsl:text>
                                        </span>
                                    </xsl:if>
                                </div>
                            </section>
                            <table>
                                <thead>
                                    <tr>
                                        <th>URL</th>
                                        <th>Last modified</th>
                                        <th>Alternates</th>
                                        <th>Images</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <xsl:for-each select="sitemap:urlset/sitemap:url">
                                        <tr>
                                            <td data-label="URL">
                                                <a href="{sitemap:loc}">
                                                    <xsl:value-of select="sitemap:loc" />
                                                </a>
                                            </td>
                                            <td data-label="Last modified">
                                                <xsl:choose>
                                                    <xsl:when test="sitemap:lastmod">
                                                        <xsl:value-of select="sitemap:lastmod" />
                                                    </xsl:when>
                                                    <xsl:otherwise>
                                                        <span class="muted">Not specified</span>
                                                    </xsl:otherwise>
                                                </xsl:choose>
                                            </td>
                                            <td data-label="Alternates">
                                                <div class="alternates">
                                                    <xsl:for-each select="xhtml:link">
                                                        <div class="alternate">
                                                            <span class="lang">
                                                                <xsl:value-of select="@hreflang" />
                                                            </span>
                                                            <a href="{@href}">
                                                                <xsl:value-of select="@href" />
                                                            </a>
                                                        </div>
                                                    </xsl:for-each>
                                                </div>
                                            </td>
                                            <td data-label="Images">
                                                <xsl:choose>
                                                    <xsl:when test="image:image">
                                                        <div class="images">
                                                            <xsl:for-each select="image:image">
                                                                <div class="image-item">
                                                                    <a href="{image:loc}">
                                                                        <xsl:value-of select="image:loc" />
                                                                    </a>
                                                                </div>
                                                            </xsl:for-each>
                                                        </div>
                                                    </xsl:when>
                                                    <xsl:otherwise>
                                                        <span class="muted">None</span>
                                                    </xsl:otherwise>
                                                </xsl:choose>
                                            </td>
                                        </tr>
                                    </xsl:for-each>
                                </tbody>
                            </table>
                        </xsl:otherwise>
                    </xsl:choose>
                </main>
            </body>
        </html>
    </xsl:template>
</xsl:stylesheet>

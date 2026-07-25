const OPENFREEMAP_GLYPH_URL = /^https:\/\/tiles\.openfreemap\.org\/fonts\/[^/]+\/([^/?]+)(\?.*)?$/;
const NOTO_SANS_FONT_STACK = 'Noto%20Sans%20Regular';

/**
 * The public Liberty style still references a retired Open Sans font stack.
 * OpenFreeMap serves Noto Sans for all required Unicode ranges instead.
 */
export function rewriteOpenFreeMapGlyphUrl(url: string, resourceType?: string): string {
  if (resourceType !== 'Glyphs') return url;
  const match = url.match(OPENFREEMAP_GLYPH_URL);
  if (!match) return url;
  return `https://tiles.openfreemap.org/fonts/${NOTO_SANS_FONT_STACK}/${match[1]}${match[2] || ''}`;
}

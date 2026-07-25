import { describe, expect, it } from 'vitest';

import { rewriteOpenFreeMapGlyphUrl } from './openfreemap-glyphs';

describe('OpenFreeMap glyph URL rewrite', () => {
  it('uses the available Noto Sans glyph stack for the Liberty style', () => {
    expect(rewriteOpenFreeMapGlyphUrl(
      'https://tiles.openfreemap.org/fonts/Open%20Sans%20Regular,Arial%20Unicode%20MS%20Regular/0-255.pbf',
      'Glyphs',
    )).toBe('https://tiles.openfreemap.org/fonts/Noto%20Sans%20Regular/0-255.pbf');
  });

  it('does not rewrite tiles or third-party glyph URLs', () => {
    expect(rewriteOpenFreeMapGlyphUrl('https://tiles.openfreemap.org/planet', 'Source')).toBe('https://tiles.openfreemap.org/planet');
    expect(rewriteOpenFreeMapGlyphUrl('https://example.test/fonts/Open%20Sans/0-255.pbf', 'Glyphs')).toBe('https://example.test/fonts/Open%20Sans/0-255.pbf');
  });
});

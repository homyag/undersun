import { describe, expect, it, vi } from 'vitest';

import { classifyMapError, createMapErrorReporter } from './map-error-policy';

describe('map error policy', () => {
  it('keeps tile and source failures recoverable', () => {
    expect(classifyMapError({ sourceId: 'openfreemap', error: new Error('Failed to load tile') }, false))
      .toEqual({ kind: 'tile', fatal: false });
    expect(classifyMapError({ sourceId: 'districts', error: new Error('Source failed') }, true))
      .toEqual({ kind: 'source', fatal: false });
  });

  it('marks initial style and WebGL failures as fatal', () => {
    expect(classifyMapError({ error: new Error('Failed to load style') }, false))
      .toEqual({ kind: 'style', fatal: true });
    expect(classifyMapError({ error: new Error('WebGL context lost') }, true))
      .toEqual({ kind: 'webgl', fatal: true });
  });

  it('reports each error kind only once', () => {
    const track = vi.fn();
    const reporter = createMapErrorReporter(track);
    const warning = { kind: 'tile' as const, fatal: false };
    reporter.report(warning, 'primary');
    reporter.report(warning, 'primary');

    expect(track).toHaveBeenCalledTimes(1);
    expect(track).toHaveBeenCalledWith('map_rebuild_map_warning', { kind: 'tile', provider: 'primary' });
  });
});

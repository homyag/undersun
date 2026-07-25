import { describe, expect, it, vi } from 'vitest';

import { createBasemapFailover } from './map-basemap-failover';

describe('basemap failover', () => {
  it('switches a failed primary style to the fallback exactly once', () => {
    const map = { once: vi.fn(), setStyle: vi.fn() };
    const report = vi.fn();
    const trackFallback = vi.fn();
    const onFatal = vi.fn();
    const fallback = createBasemapFailover({
      map,
      fallbackStyle: { version: 8, sources: {}, layers: [] },
      report,
      trackFallback,
      onStyleReady: vi.fn(),
      onFatal,
    });
    const styleFailure = { kind: 'style' as const, fatal: true };

    fallback.handle(styleFailure);
    fallback.handle(styleFailure);

    expect(map.setStyle).toHaveBeenCalledTimes(1);
    expect(trackFallback).toHaveBeenCalledTimes(1);
    expect(report).toHaveBeenNthCalledWith(1, styleFailure, 'primary');
    expect(report).toHaveBeenNthCalledWith(2, styleFailure, 'fallback');
    expect(onFatal).toHaveBeenCalledTimes(1);
  });
});

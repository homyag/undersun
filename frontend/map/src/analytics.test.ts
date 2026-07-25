import { describe, expect, it, vi } from 'vitest';

import { trackMapEvent, trackMapTiming } from './analytics';

describe('map analytics', () => {
  it('sends only the supplied aggregate event params', () => {
    const dispatch = vi.fn();
    window.dispatchMetrikaGoal = dispatch;
    trackMapEvent('map_rebuild_property_selected', { source: 'map' });
    trackMapTiming('api', 12.6, { mode: 'properties' });

    expect(dispatch).toHaveBeenNthCalledWith(1, 'map_rebuild_property_selected', { source: 'map' });
    expect(dispatch).toHaveBeenNthCalledWith(2, 'map_rebuild_timing', { stage: 'api', duration_ms: 13, mode: 'properties' });
  });
});

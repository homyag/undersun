const MAP_VISIT_COUNT_KEY = 'undersun-map-visit-count';
const MAP_SESSION_RECORDED_KEY = 'undersun-map-session-recorded';
const MAX_REPORTED_VISIT_COUNT = 9;

export type MapSessionUsage = {
  isReturning: boolean;
  visitCount: number;
};

/**
 * Records a map visit locally and reports only an anonymous, capped count.
 * Search criteria and any user identifiers intentionally never enter analytics.
 */
export function recordMapSessionUsage(storage: Storage = window.localStorage, sessionStorage: Storage = window.sessionStorage): MapSessionUsage | null {
  try {
    if (sessionStorage.getItem(MAP_SESSION_RECORDED_KEY) === '1') return null;

    const previousCount = Number.parseInt(storage.getItem(MAP_VISIT_COUNT_KEY) || '0', 10);
    const normalizedPreviousCount = Number.isFinite(previousCount) && previousCount > 0 ? previousCount : 0;
    const nextCount = normalizedPreviousCount + 1;

    storage.setItem(MAP_VISIT_COUNT_KEY, String(nextCount));
    sessionStorage.setItem(MAP_SESSION_RECORDED_KEY, '1');

    return {
      isReturning: normalizedPreviousCount > 0,
      visitCount: Math.min(nextCount, MAX_REPORTED_VISIT_COUNT),
    };
  } catch {
    // Private browsing or restrictive privacy settings can disable Web Storage.
    return null;
  }
}

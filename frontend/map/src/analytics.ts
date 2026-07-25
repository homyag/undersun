type AnalyticsParams = Record<string, boolean | number | string>;

declare global {
  interface Window {
    dispatchMetrikaGoal?: (name: string, params?: AnalyticsParams) => void;
  }
}

export function trackMapEvent(name: string, params: AnalyticsParams = {}): void {
  window.dispatchMetrikaGoal?.(name, params);
}

export function trackMapTiming(stage: string, durationMs: number, extra: AnalyticsParams = {}): void {
  trackMapEvent('map_rebuild_timing', { stage, duration_ms: Math.round(durationMs), ...extra });
}

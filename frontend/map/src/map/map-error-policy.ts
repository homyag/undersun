export type MapErrorKind = 'style' | 'webgl' | 'tile' | 'source' | 'runtime';

type MapErrorEvent = {
  error?: unknown;
  sourceId?: unknown;
};

export type MapErrorDecision = {
  kind: MapErrorKind;
  fatal: boolean;
};

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message.toLowerCase();
  return String(error || '').toLowerCase();
}

export function classifyMapError(event: MapErrorEvent, isStyleLoaded: boolean): MapErrorDecision {
  const message = getErrorMessage(event.error);
  if (/webgl|context.*lost|context.*fail/.test(message)) return { kind: 'webgl', fatal: true };
  if (typeof event.sourceId === 'string' && event.sourceId) {
    return { kind: /tile|raster|vector/.test(message) ? 'tile' : 'source', fatal: false };
  }
  if (/tile|tilejson/.test(message)) return { kind: 'tile', fatal: false };
  if (!isStyleLoaded || /style|stylesheet|sprite|glyph/.test(message)) return { kind: 'style', fatal: true };
  return { kind: 'runtime', fatal: false };
}

export function createMapErrorReporter(track: (name: string, params: Record<string, string>) => void) {
  const reportedKinds = new Set<MapErrorKind>();

  return {
    report(decision: MapErrorDecision, provider: 'primary' | 'fallback') {
      if (reportedKinds.has(decision.kind)) return;
      reportedKinds.add(decision.kind);
      track(decision.fatal ? 'map_rebuild_map_fatal' : 'map_rebuild_map_warning', {
        kind: decision.kind,
        provider,
      });
    },
  };
}

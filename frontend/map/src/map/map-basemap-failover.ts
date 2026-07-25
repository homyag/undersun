import type { MapErrorDecision, MapErrorKind } from './map-error-policy';
import type { StyleSpecification } from 'maplibre-gl';

type StyleMap = {
  once: (event: 'style.load', callback: () => void) => void;
  setStyle: (style: StyleSpecification) => unknown;
};

type BasemapFailoverOptions = {
  map: StyleMap;
  fallbackStyle: StyleSpecification;
  report: (decision: MapErrorDecision, provider: 'primary' | 'fallback') => void;
  trackFallback: (reason: MapErrorKind) => void;
  onStyleReady: () => void;
  onFatal: () => void;
};

export function createBasemapFailover(options: BasemapFailoverOptions) {
  let fallbackActive = false;

  return {
    handle(decision: MapErrorDecision) {
      options.report(decision, fallbackActive ? 'fallback' : 'primary');
      if (!decision.fatal) return;
      if (decision.kind === 'style' && !fallbackActive) {
        fallbackActive = true;
        options.trackFallback(decision.kind);
        options.map.once('style.load', options.onStyleReady);
        options.map.setStyle(options.fallbackStyle);
        return;
      }
      options.onFatal();
    },
    isFallbackActive: () => fallbackActive,
  };
}

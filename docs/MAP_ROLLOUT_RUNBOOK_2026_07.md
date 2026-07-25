# Map Rollout Runbook

## Preconditions

1. Build frontend assets before deployment:

   ```bash
   cd frontend/map
   npm ci
   npm run lint
   npm test
   npm run test:e2e
   npm run build
   cd ../..
   python manage.py collectstatic --noinput
   ```

2. Confirm the deployed `static/map-app/manifest.json` and its hashed assets are served with HTTP `200`.
3. Confirm `/ru/map/`, `/en/map/`, `/th/map/` retain title, canonical/hreflang and JSON-LD when the flag is enabled.
4. Verify rollback before exposing the new shell:

   ```env
   MAP_REBUILD_ENABLED=0
   ```

   Restart the application and confirm that `/map/` serves legacy `core/map.html`.

5. Verify the in-app basemap failover once in staging: force the primary style URL to return `404`, reload `/ru/map/`, and confirm that the map switches once to the OpenStreetMap raster fallback while property pins and the result list remain available. Restore the primary URL after the check.

## Flag Stages

| Stage | Flags | Audience | Exit criterion |
| --- | --- | --- | --- |
| Internal | `MAP_REBUILD_ENABLED=1`, `MAP_REBUILD_STAFF_ONLY=1` | authenticated Django staff | manual device checks and no blocking JS/API errors |
| Canary | `MAP_REBUILD_ENABLED=1`, `MAP_REBUILD_STAFF_ONLY=0` plus upstream traffic split | 10% of map traffic | 24 hours within budgets |
| Expansion | same | 50% of map traffic | 72 hours within budgets |
| Full | same | 100% | 7 days within budgets before legacy-removal PR |

The current Django flag supports staff-only gating. A percentage canary must be implemented at the reverse proxy/CDN or as a separate deterministic server-side cohort flag; do not use client-side randomness.

## Metrika Dashboard

Create a dashboard scoped to map sessions with these event groups:

| Goal | Breakdown | Purpose |
| --- | --- | --- |
| `map_rebuild_filters_changed` | `active_filter_count` | filter adoption |
| `map_rebuild_viewport_search` | - | deliberate viewport search |
| `map_rebuild_property_selected` | `source` | marker-to-card funnel |
| `map_rebuild_favorite_changed` | `active` | shortlist intent |
| `map_rebuild_map_error` | - | client map failures |
| `map_rebuild_map_warning` | `kind`, `provider` | one aggregated tile/source/runtime warning per session |
| `map_rebuild_map_fatal` | `kind`, `provider` | fatal style/WebGL failure, deduplicated by kind |
| `map_rebuild_basemap_fallback` | `from`, `to`, `reason` | primary OpenFreeMap style switched to OSM raster fallback |
| `map_rebuild_timing` | `stage`, `mode`, `duration_ms` | API/client latency |

Never add property ID, slug, search query, coordinates, user contact data, IP address or other PII as a goal parameter.

Dashboard cards:

1. Map sessions, filter changes, viewport searches, property selections, detail exits and favourite changes.
2. `map_rebuild_timing`: p75/p95 separately for `api` and `client_results`, split by `mode`.
3. `map_rebuild_map_warning`, `map_rebuild_map_fatal` and `map_rebuild_basemap_fallback` rates per map session.
4. Count of rollbacks/flag disablements from deployment log.

## Stop And Rollback Conditions

Immediately set `MAP_REBUILD_ENABLED=0` and restart the app when any condition is sustained for 15 minutes after excluding an external provider outage:

- map JavaScript error rate is at least `0.5%` of map sessions;
- API p95 is above `1.5 s` for normal property viewport;
- map shell is blank, cards/sheets are clipped, or filters cannot be operated with keyboard/touch;
- price, language, favourites, detail URL, or map-result count regress compared with legacy;
- OpenFreeMap style/tile failure makes the base map unusable.

Record timestamp, release revision, user impact, observed metrics and rollback result in the deployment log.

## Manual Device Audit

Before canary, test with a staff account:

- Safari on iOS: filters, result sheet, favourite, detail link, denied geolocation.
- Chrome on Android: the same flow plus keyboard focus where available.
- Chrome DevTools Slow 4G: shell visible, first results and filter-to-results timings.
- Keyboard-only desktop: filter controls, chips, map card close and mobile-sheet focus trap.
- Reduced-motion: no nonessential animation and no disorienting camera movement.

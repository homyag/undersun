import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { MapApp, MapErrorBoundary, MapFallback } from './app';
import { getMapBootstrap } from './bootstrap';
import './styles.css';
import 'maplibre-gl/dist/maplibre-gl.css';

const mountNode = document.getElementById('property-map-app');
const queryClient = new QueryClient();

if (mountNode) {
  const root = createRoot(mountNode);

  try {
    const bootstrap = getMapBootstrap(document);
    mountNode.dataset.currencyHandler = 'true';
    root.render(
      <StrictMode>
        <QueryClientProvider client={queryClient}>
          <MapErrorBoundary fallback={<MapFallback message={bootstrap.translations.unavailable} />}>
            <MapApp bootstrap={bootstrap} />
          </MapErrorBoundary>
        </QueryClientProvider>
      </StrictMode>,
    );
  } catch (error) {
    console.error('Map application bootstrap failed.', error);
    root.render(<MapFallback message="Map is temporarily unavailable." />);
  }
}

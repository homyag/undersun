import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { MapContentState } from './map-content-state';

describe('MapContentState', () => {
  it('offers retry after a request error', () => {
    const retry = vi.fn();
    render(<MapContentState isPending={false} isError resultCount={undefined} loadingLabel="Loading" unavailableLabel="Unavailable" noResultsLabel="Empty" retryLabel="Retry" resetLabel="Reset" onRetry={retry} onReset={vi.fn()} />);

    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it('offers reset for an empty result', () => {
    const reset = vi.fn();
    render(<MapContentState isPending={false} isError={false} resultCount={0} loadingLabel="Loading" unavailableLabel="Unavailable" noResultsLabel="Empty" retryLabel="Retry" resetLabel="Reset" onRetry={vi.fn()} onReset={reset} />);

    fireEvent.click(screen.getByRole('button', { name: 'Reset' }));
    expect(reset).toHaveBeenCalledOnce();
  });

  it('does not render a separate result count after a successful request', () => {
    const { container } = render(<MapContentState isPending={false} isError={false} resultCount={154} loadingLabel="Loading" unavailableLabel="Unavailable" noResultsLabel="Empty" retryLabel="Retry" resetLabel="Reset" onRetry={vi.fn()} onReset={vi.fn()} />);

    expect(container).toBeEmptyDOMElement();
  });
});

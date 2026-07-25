import { useEffect, useRef } from 'react';

import type { MapAppBootstrap } from '../../bootstrap';
import type { MapSearchState } from './state';
import { FilterSidebar } from './filter-sidebar';

type MobileFilterSheetProps = {
  bootstrap: MapAppBootstrap;
  state: MapSearchState;
  resultCount: number | undefined;
  resultCountLabel: string;
  onChange: (state: MapSearchState) => void;
  onClose: () => void;
};

export function MobileFilterSheet({ bootstrap, state, resultCount, resultCountLabel, onChange, onClose }: MobileFilterSheetProps) {
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    dialogRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
        return;
      }
      if (event.key !== 'Tab' || !dialogRef.current) return;
      const focusable = [...dialogRef.current.querySelectorAll<HTMLElement>('button, input, select, [href], [tabindex]:not([tabindex="-1"])')]
        .filter((element) => !element.hasAttribute('disabled'));
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [onClose]);

  return <div className="map-filter-sheet-backdrop" onMouseDown={onClose}>
    <div className="map-filter-sheet" role="dialog" aria-modal="true" aria-label={bootstrap.translations.filters}
      ref={dialogRef} tabIndex={-1} onMouseDown={(event) => event.stopPropagation()}>
      <header><strong>{bootstrap.translations.filters}</strong><button type="button" onClick={onClose} aria-label={bootstrap.translations.close}>×</button></header>
      <FilterSidebar bootstrap={bootstrap} state={state} resultCount={resultCount} resultCountLabel={resultCountLabel} onChange={onChange} className="map-filter-sidebar--mobile" />
      <footer><button type="button" onClick={onClose}>{bootstrap.translations.showResults} {resultCount ?? '...'} {resultCountLabel}</button></footer>
    </div>
  </div>;
}

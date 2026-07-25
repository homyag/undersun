type MapContentStateProps = {
  isPending: boolean;
  isError: boolean;
  resultCount: number | undefined;
  loadingLabel: string;
  unavailableLabel: string;
  noResultsLabel: string;
  retryLabel: string;
  resetLabel: string;
  onRetry: () => void;
  onReset: () => void;
};

export function MapContentState(props: MapContentStateProps) {
  if (props.isPending) return <div className="map-content-state" role="status" aria-busy="true"><span className="map-content-state__skeleton" />{props.loadingLabel}</div>;
  if (props.isError) return <div className="map-content-state" role="alert">{props.unavailableLabel}<button type="button" onClick={props.onRetry}>{props.retryLabel}</button></div>;
  if (props.resultCount === 0) return <div className="map-content-state" role="status">{props.noResultsLabel}<button type="button" onClick={props.onReset}>{props.resetLabel}</button></div>;
  return null;
}

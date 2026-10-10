export default function LoadingState({ title, detail, progress }) {
  return (
    <div className="loading" role="status" aria-live="polite">
      <div className="spinner" aria-hidden="true" />
      <div className="loading-text">
        <strong>{title}</strong>
        {detail && <span>{detail}</span>}
        {typeof progress === "number" && (
          <div className="progress" aria-label="Upload progress">
            <div className="progress-bar" style={{ width: `${progress}%` }} />
          </div>
        )}
      </div>
    </div>
  );
}

import { AlertTriangle, XCircle } from "lucide-react";

/** tone: "bad" (processing error, red) | "warn" (amber) */
export default function ErrorMessage({ title, children, tone = "bad", onRetry }) {
  const Icon = tone === "warn" ? AlertTriangle : XCircle;
  return (
    <div className={`alert alert-${tone}`} role={tone === "bad" ? "alert" : "status"}>
      <Icon size={18} aria-hidden="true" />
      <div>
        {title && <strong>{title}</strong>}
        <div>{children}</div>
        {onRetry && (
          <button type="button" className="btn btn-quiet" onClick={onRetry}>Try again</button>
        )}
      </div>
    </div>
  );
}

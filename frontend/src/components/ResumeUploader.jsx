import { useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, FileText, Loader2, UploadCloud, XCircle, X } from "lucide-react";
import { formatBytes } from "../utils/format.js";

const STATUS_META = {
  ready: { label: "Ready", tone: "info", Icon: FileText },
  uploading: { label: "Uploading", tone: "info", Icon: Loader2 },
  analyzing: { label: "Analyzing", tone: "info", Icon: Loader2 },
  processed: { label: "Processed", tone: "good", Icon: CheckCircle2 },
  warning: { label: "Processed with warnings", tone: "warn", Icon: AlertTriangle },
  failed: { label: "Failed", tone: "bad", Icon: XCircle },
};

/** items: [{ id, file, status, message, warnings }] */
export default function ResumeUploader({ items, onAdd, onRemove, busy, uploadProgress, maxFiles, maxSizeMb }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);

  const handleFiles = (list) => {
    if (list && list.length) onAdd(Array.from(list));
    if (inputRef.current) inputRef.current.value = "";
  };

  return (
    <div>
      <div
        className={`dropzone ${dragging ? "dragging" : ""} ${busy ? "disabled" : ""}`}
        onDragOver={(e) => { e.preventDefault(); if (!busy) setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); if (!busy) handleFiles(e.dataTransfer.files); }}
      >
        <UploadCloud size={28} aria-hidden="true" />
        <p>
          <label htmlFor="resume-input" className="link-label">Choose resumes</label> or drop them here
        </p>
        <p className="hint">PDF or DOCX, up to {maxSizeMb} MB each, {maxFiles} files per analysis.</p>
        <input
          ref={inputRef}
          id="resume-input"
          className="sr-only-input"
          type="file"
          multiple
          accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          disabled={busy}
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>

      {items.length === 0 ? (
        <p className="hint file-empty">No resumes added yet.</p>
      ) : (
        <ul className="file-list" aria-label="Selected resumes">
          {items.map((item) => {
            const meta = STATUS_META[item.status] || STATUS_META.ready;
            const Icon = meta.Icon;
            const spin = item.status === "uploading" || item.status === "analyzing";
            const label = item.status === "uploading" && uploadProgress != null ? `Uploading ${uploadProgress}%` : meta.label;
            return (
              <li key={item.id} className="file-row">
                <FileText size={18} aria-hidden="true" className="file-icon" />
                <div className="file-main">
                  <span className="file-name" title={item.file.name}>{item.file.name}</span>
                  <span className="file-size">{formatBytes(item.file.size)}</span>
                  {item.message && <span className={`file-msg tone-text-${meta.tone}`}>{item.message}</span>}
                  {item.warnings?.map((w) => (
                    <span key={w} className="file-msg tone-text-warn">{w}</span>
                  ))}
                </div>
                <span className={`status-pill tone-${meta.tone}`}>
                  <Icon size={14} aria-hidden="true" className={spin ? "spin" : ""} />
                  {label}
                </span>
                <button
                  type="button"
                  className="icon-btn"
                  aria-label={`Remove ${item.file.name}`}
                  disabled={busy}
                  onClick={() => onRemove(item.id)}
                >
                  <X size={16} aria-hidden="true" />
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

import { useId } from "react";
import { Info } from "lucide-react";

/** Keyboard-focusable tooltip. */
export default function InfoTip({ text, label = "More information" }) {
  const id = useId();
  return (
    <span className="infotip">
      <button type="button" className="infotip-btn" aria-label={label} aria-describedby={id}>
        <Info size={14} aria-hidden="true" />
      </button>
      <span role="tooltip" id={id} className="infotip-bubble">{text}</span>
    </span>
  );
}

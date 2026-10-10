import { useId, useState } from "react";
import { X } from "lucide-react";

/** Chip input: type a skill and press Enter or comma. Backspace on empty input removes the last chip. */
export default function SkillInput({ label, hint, value, onChange, placeholder }) {
  const id = useId();
  const [draft, setDraft] = useState("");

  const commit = (raw) => {
    const parts = raw.split(/[,;\n]+/).map((s) => s.trim()).filter(Boolean);
    if (!parts.length) return;
    const next = [...value];
    parts.forEach((p) => {
      if (!next.some((v) => v.toLowerCase() === p.toLowerCase())) next.push(p);
    });
    onChange(next);
    setDraft("");
  };

  const onKeyDown = (e) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      commit(draft);
    } else if (e.key === "Backspace" && !draft && value.length) {
      onChange(value.slice(0, -1));
    }
  };

  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <div className="chip-input">
        {value.map((skill) => (
          <span className="badge badge-info chip" key={skill}>
            {skill}
            <button type="button" aria-label={`Remove ${skill}`} onClick={() => onChange(value.filter((v) => v !== skill))}>
              <X size={12} aria-hidden="true" />
            </button>
          </span>
        ))}
        <input
          id={id}
          value={draft}
          placeholder={value.length ? "" : placeholder}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
          onBlur={() => commit(draft)}
          aria-describedby={`${id}-hint`}
        />
      </div>
      <p className="hint" id={`${id}-hint`}>{hint}</p>
    </div>
  );
}

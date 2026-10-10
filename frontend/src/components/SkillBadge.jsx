import { Check } from "lucide-react";

/**
 * variant: "found" (green) | "missing" (neutral, "not found in resume") | "info" (blue)
 * Missing skills are deliberately neutral: absence from the text is not a judgement of the person.
 */
export default function SkillBadge({ children, variant = "info" }) {
  return (
    <span className={`badge badge-${variant}`}>
      {variant === "found" && <Check size={12} aria-hidden="true" />}
      {children}
      {variant === "missing" && <span className="sr-only"> (not found in resume)</span>}
    </span>
  );
}

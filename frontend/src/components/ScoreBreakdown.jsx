import InfoTip from "./InfoTip.jsx";
import { fmtScore, scoreTone } from "../utils/format.js";

const SEGMENT_CLASS = {
  required_skills: "seg-required",
  semantic_similarity: "seg-semantic",
  preferred_skills: "seg-preferred",
};

const TIPS = {
  required_skills: "Share of the required skills that were found in the resume text. Absence means 'not found in the text', not that the person lacks the skill.",
  preferred_skills: "Share of the preferred skills that were found in the resume text.",
  semantic_similarity: "How close the overall meaning of the resume is to the job description, from a pretrained language model, scaled to 0–100.",
};

/** Stacked bar: how many of the 100 points each component contributed. */
export function CompositionBar({ components, compact = false }) {
  return (
    <div className={`composition ${compact ? "compact" : ""}`} role="img"
      aria-label={components.filter((c) => c.available).map((c) => `${c.label}: ${fmtScore(c.contribution)} points`).join(", ")}>
      {components.filter((c) => c.available && c.contribution > 0).map((c) => (
        <span key={c.key} className={`seg ${SEGMENT_CLASS[c.key]}`} style={{ width: `${c.contribution}%` }} />
      ))}
    </div>
  );
}

export default function ScoreBreakdown({ breakdown }) {
  return (
    <div className="breakdown">
      <div className="breakdown-head">
        <div>
          <span className="big-score">{fmtScore(breakdown.final_score)}</span>
          <span className="big-score-unit"> / 100</span>
        </div>
        <InfoTip label="About this score" text="An estimate of similarity to the job description. It is not a probability of hiring success and should support, not replace, human review." />
      </div>
      <CompositionBar components={breakdown.components} />
      <table className="table-plain">
        <thead>
          <tr>
            <th scope="col">Component</th>
            <th scope="col" className="num">Score</th>
            <th scope="col" className="num">Weight used</th>
            <th scope="col" className="num">Adds</th>
          </tr>
        </thead>
        <tbody>
          {breakdown.components.map((c) => (
            <tr key={c.key} className={c.available ? "" : "muted-row"}>
              <th scope="row">
                <span className={`swatch ${SEGMENT_CLASS[c.key]}`} aria-hidden="true" />
                {c.label}
                <InfoTip label={`About ${c.label}`} text={TIPS[c.key]} />
                <div className="cell-detail">{c.detail}</div>
              </th>
              <td className={`num ${c.available ? `tone-text-${scoreTone(c.score)}` : ""}`}>
                {c.available ? `${fmtScore(c.score)}%` : "n/a"}
              </td>
              <td className="num">{c.available ? `${Math.round(c.effective_weight * 100)}%` : "—"}</td>
              <td className="num">{c.available ? `${fmtScore(c.contribution)} pts` : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {breakdown.notes.map((n) => (
        <p className="note" key={n}>{n}</p>
      ))}
      <p className="hint">Scoring configuration v{breakdown.scoring_version}</p>
    </div>
  );
}

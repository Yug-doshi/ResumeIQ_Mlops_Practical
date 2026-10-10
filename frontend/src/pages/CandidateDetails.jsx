import { Link, useParams } from "react-router-dom";
import { AlertTriangle, ArrowLeft, ExternalLink, FileText } from "lucide-react";
import ScoreBreakdown from "../components/ScoreBreakdown.jsx";
import SkillBadge from "../components/SkillBadge.jsx";
import ErrorMessage from "../components/ErrorMessage.jsx";
import { useResults } from "../context/ResultsContext.jsx";
import { downloadBlob } from "../utils/format.js";

function SkillGroup({ title, found, missing }) {
  if (found.length + missing.length === 0) return null;
  return (
    <div className="skill-group">
      <h3>{title}</h3>
      {found.length > 0 && (
        <div>
          <p className="group-label">Found in resume</p>
          <div className="badges">{found.map((s) => <SkillBadge key={s} variant="found">{s}</SkillBadge>)}</div>
        </div>
      )}
      {missing.length > 0 && (
        <div>
          <p className="group-label">Not found in resume</p>
          <div className="badges">{missing.map((s) => <SkillBadge key={s} variant="missing">{s}</SkillBadge>)}</div>
        </div>
      )}
    </div>
  );
}

export default function CandidateDetails() {
  const { resumeId } = useParams();
  const { result, sentFiles } = useResults();
  const candidate = result?.candidates.find((c) => c.resume_id === resumeId);

  if (!candidate) {
    return (
      <main className="page">
        <div className="empty">
          <h1>Candidate not available</h1>
          <p>Results are kept only in this browser tab. If you refreshed the page or started a new analysis, run the analysis again.</p>
          <Link className="btn btn-primary" to="/">Back to dashboard</Link>
        </div>
      </main>
    );
  }

  const file = sentFiles[candidate.upload_index];
  const openOriginal = () => {
    if (!file) return;
    if (file.name.toLowerCase().endsWith(".pdf")) {
      const url = URL.createObjectURL(file);
      window.open(url, "_blank", "noopener");
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } else {
      downloadBlob(file, file.name);
    }
  };

  const evidenceBySkill = candidate.evidence.reduce((acc, e) => {
    (acc[e.skill] ||= []).push(e);
    return acc;
  }, {});
  const exp = candidate.experience;

  return (
    <main className="page">
      <Link to="/" className="back-link"><ArrowLeft size={16} aria-hidden="true" /> Back to results</Link>

      <div className="detail-head">
        <div>
          <h1 className="detail-title"><FileText size={22} aria-hidden="true" /> {candidate.filename}</h1>
          <p className="hint">Rank {candidate.rank} of {result.candidates.length} for {result.job.job_title}</p>
        </div>
        <button type="button" className="btn btn-secondary" onClick={openOriginal} disabled={!file}>
          <ExternalLink size={16} aria-hidden="true" />
          {file?.name.toLowerCase().endsWith(".pdf") ? "Open original resume" : "Download original resume"}
        </button>
      </div>
      <p className="hint">The original is opened from your computer. It is not stored by the server.</p>

      <p className="disclaimer">{result.score_disclaimer}</p>

      {candidate.warnings.length > 0 && (
        <ErrorMessage tone="warn" title="Processing warnings">
          <ul className="error-list">{candidate.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
        </ErrorMessage>
      )}

      <div className="detail-grid">
        <section className="panel" aria-labelledby="score-title">
          <h2 id="score-title">Score breakdown</h2>
          <ScoreBreakdown breakdown={candidate.score_breakdown} />
          <dl className="meta">
            <div><dt>Semantic similarity (raw cosine)</dt><dd>{candidate.semantic_cosine}</dd></div>
            <div><dt>Model</dt><dd>{candidate.model_id}</dd></div>
            <div><dt>Characters analysed</dt><dd>{candidate.extracted_characters.toLocaleString()}</dd></div>
          </dl>
        </section>

        <section className="panel" aria-labelledby="skills-title">
          <h2 id="skills-title">Skills</h2>
          <SkillGroup title="Required skills" found={candidate.required_matched} missing={candidate.required_not_found} />
          <SkillGroup title="Preferred skills" found={candidate.preferred_matched} missing={candidate.preferred_not_found} />
          <div className="skill-group">
            <h3>Technical skills detected in resume</h3>
            {candidate.extracted_skills.length ? (
              <div className="badges">{candidate.extracted_skills.map((s) => <SkillBadge key={s} variant="info">{s}</SkillBadge>)}</div>
            ) : <p className="hint">No dictionary skills were detected.</p>}
            <p className="hint">Detection uses a configurable skill list and does not find every skill a resume may contain.</p>
          </div>
        </section>
      </div>

      <section className="panel" aria-labelledby="evidence-title">
        <h2 id="evidence-title">Evidence from the resume</h2>
        {Object.keys(evidenceBySkill).length === 0 ? (
          <p className="hint">No required or preferred skills were found in the text, so there are no excerpts to show.</p>
        ) : (
          <ul className="evidence">
            {Object.entries(evidenceBySkill).map(([skill, list]) => (
              <li key={skill}>
                <SkillBadge variant="found">{skill}</SkillBadge>
                {list.map((e) => (
                  <blockquote key={`${e.line}-${e.snippet}`}>
                    {e.snippet}
                    <cite>line {e.line} of the extracted text</cite>
                  </blockquote>
                ))}
              </li>
            ))}
          </ul>
        )}
        <p className="hint">
          Excerpts are copied from the extracted resume text; e-mail addresses and phone numbers are masked. A mention
          shows the skill appears in the text, not how well the candidate has used it.
        </p>
      </section>

      <section className="panel" aria-labelledby="exp-title">
        <h2 id="exp-title">Experience</h2>
        {exp.status === "not_requested" && <p className="hint">{exp.note}</p>}
        {exp.status !== "not_requested" && (
          <>
            <p>Requirement: at least <strong>{exp.required_years}</strong> years.</p>
            {exp.status === "mentions_found" ? (
              <>
                <p>Highest stated: <strong>{exp.max_stated_years}</strong> years (unverified).</p>
                <ul className="evidence">
                  {exp.mentions.map((m) => (
                    <li key={`${m.line}-${m.snippet}`}>
                      <blockquote>{m.snippet}<cite>line {m.line} of the extracted text</cite></blockquote>
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              <p className="tone-text-warn warn-count"><AlertTriangle size={14} aria-hidden="true" /> No explicit statement of years of experience was found.</p>
            )}
            <p className="hint">{exp.note}</p>
          </>
        )}
        {result.job.education_requirement && (
          <p className="hint">Education requirement recorded for review: “{result.job.education_requirement}”. It is not evaluated automatically.</p>
        )}
      </section>
    </main>
  );
}

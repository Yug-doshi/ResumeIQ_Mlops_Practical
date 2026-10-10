import { useMemo, useState } from "react";
import { AlertTriangle, ChevronRight, Search } from "lucide-react";
import { CompositionBar } from "./ScoreBreakdown.jsx";
import InfoTip from "./InfoTip.jsx";
import { fmtScore, scoreTone } from "../utils/format.js";

const SORTS = {
  score_desc: { label: "Score: high to low", fn: (a, b) => b.score - a.score || a.rank - b.rank },
  score_asc: { label: "Score: low to high", fn: (a, b) => a.score - b.score || a.rank - b.rank },
  semantic_desc: { label: "Semantic similarity: high to low", fn: (a, b) => b.semantic_score - a.semantic_score },
  name_asc: { label: "Filename: A to Z", fn: (a, b) => a.filename.localeCompare(b.filename) },
};

export function useVisibleCandidates(candidates, { query, sortKey, skills }) {
  return useMemo(() => {
    const q = query.trim().toLowerCase();
    return candidates
      .filter((c) => !q || c.filename.toLowerCase().includes(q))
      .filter((c) => skills.every((s) => c.extracted_skills.includes(s)))
      .sort(SORTS[sortKey].fn);
  }, [candidates, query, sortKey, skills]);
}

export function CandidateToolbar({ candidates, query, setQuery, sortKey, setSortKey, skills, setSkills, shown }) {
  const allSkills = useMemo(
    () => [...new Set(candidates.flatMap((c) => c.extracted_skills))].sort((a, b) => a.localeCompare(b)),
    [candidates]
  );
  const toggle = (s) => setSkills(skills.includes(s) ? skills.filter((x) => x !== s) : [...skills, s]);
  return (
    <div className="toolbar">
      <div className="search">
        <Search size={16} aria-hidden="true" />
        <label htmlFor="search" className="sr-only">Search by filename</label>
        <input id="search" type="search" placeholder="Search by filename" value={query} onChange={(e) => setQuery(e.target.value)} />
      </div>
      <div className="field inline">
        <label htmlFor="sort">Sort by</label>
        <select id="sort" value={sortKey} onChange={(e) => setSortKey(e.target.value)}>
          {Object.entries(SORTS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
      </div>
      <details className="filter">
        <summary>
          Skills found{skills.length ? ` (${skills.length})` : ""}
        </summary>
        <div className="filter-panel" role="group" aria-label="Filter by skills found in resume">
          {allSkills.length === 0 && <p className="hint">No skills were found in these resumes.</p>}
          {allSkills.map((s) => (
            <label key={s} className="check">
              <input type="checkbox" checked={skills.includes(s)} onChange={() => toggle(s)} />
              {s}
            </label>
          ))}
          {skills.length > 0 && <button type="button" className="btn btn-quiet" onClick={() => setSkills([])}>Clear filter</button>}
        </div>
      </details>
      <span className="toolbar-count" aria-live="polite">{shown} of {candidates.length} shown</span>
    </div>
  );
}

export default function CandidateTable({ rows, hasJobSkills, onOpen }) {
  if (rows.length === 0) {
    return (
      <div className="empty compact">
        <p><strong>No candidates match the current search or filter.</strong></p>
        <p className="hint">Clear the search box or the skills filter to see all results.</p>
      </div>
    );
  }
  return (
    <div className="table-wrap">
      <table className="candidates">
        <thead>
          <tr>
            <th scope="col" className="num">Rank</th>
            <th scope="col">Resume file</th>
            <th scope="col">
              Matching score <InfoTip label="About the matching score" text="0–100 estimate of similarity to the job description, split into skills and semantic parts. Not a hiring decision." />
            </th>
            <th scope="col" className="num">Semantic</th>
            {hasJobSkills && <th scope="col">Required found</th>}
            {hasJobSkills && <th scope="col">Preferred found</th>}
            <th scope="col">Warnings</th>
            <th scope="col"><span className="sr-only">Open</span></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => (
            <tr key={c.resume_id}>
              <td className="num">{c.rank}</td>
              <td>
                <button type="button" className="link-btn" onClick={() => onOpen(c)}>{c.filename}</button>
              </td>
              <td>
                <div className="score-cell">
                  <strong className={`tone-text-${scoreTone(c.score)}`}>{fmtScore(c.score)}</strong>
                  <CompositionBar components={c.score_breakdown.components} compact />
                </div>
              </td>
              <td className={`num tone-text-${scoreTone(c.semantic_score)}`}>{fmtScore(c.semantic_score)}%</td>
              {hasJobSkills && (
                <td>{c.required_matched.length + c.required_not_found.length > 0
                  ? `${c.required_matched.length} of ${c.required_matched.length + c.required_not_found.length}` : "—"}</td>
              )}
              {hasJobSkills && (
                <td>{c.preferred_matched.length + c.preferred_not_found.length > 0
                  ? `${c.preferred_matched.length} of ${c.preferred_matched.length + c.preferred_not_found.length}` : "—"}</td>
              )}
              <td>
                {c.warnings.length > 0 ? (
                  <span className="tone-text-warn warn-count"><AlertTriangle size={14} aria-hidden="true" />{c.warnings.length}<span className="sr-only"> warnings</span></span>
                ) : <span className="muted">None</span>}
              </td>
              <td>
                <button type="button" className="btn btn-quiet" onClick={() => onOpen(c)} aria-label={`View details for ${c.filename}`}>
                  Details <ChevronRight size={14} aria-hidden="true" />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

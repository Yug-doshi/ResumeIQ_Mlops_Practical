import { createContext, useContext, useMemo, useState } from "react";

/**
 * In-memory session state shared between the dashboard and the candidate page.
 * Nothing is written to localStorage/sessionStorage, so resume-derived text disappears when the
 * tab is refreshed or closed. `sentFiles` keeps the File objects so a reviewer can open the
 * original resume locally; the server never keeps them.
 */
const ResultsContext = createContext(null);

export const EMPTY_JOB = {
  jobTitle: "",
  jobDescription: "",
  requiredSkills: [],
  preferredSkills: [],
  minExperienceYears: "",
  educationRequirement: "",
};

export const DEFAULT_VIEW = { query: "", sortKey: "score_desc", skills: [] };

export function ResultsProvider({ children }) {
  const [result, setResult] = useState(null);
  const [sentFiles, setSentFiles] = useState([]);
  const [job, setJob] = useState(EMPTY_JOB);
  const [items, setItems] = useState([]);
  const [view, setView] = useState(DEFAULT_VIEW);

  const value = useMemo(
    () => ({
      result, sentFiles, job, setJob, items, setItems, view, setView,
      setAnalysis: (r, files) => { setResult(r); setSentFiles(files); setView(DEFAULT_VIEW); },
      clearAll: () => { setResult(null); setSentFiles([]); setItems([]); setView(DEFAULT_VIEW); },
    }),
    [result, sentFiles, job, items, view]
  );
  return <ResultsContext.Provider value={value}>{children}</ResultsContext.Provider>;
}

export function useResults() {
  const ctx = useContext(ResultsContext);
  if (!ctx) throw new Error("useResults must be used inside ResultsProvider");
  return ctx;
}

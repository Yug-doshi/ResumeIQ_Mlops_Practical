import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Download, Loader2, RotateCcw, Sparkles } from "lucide-react";
import JobDescriptionForm from "../components/JobDescriptionForm.jsx";
import ResumeUploader from "../components/ResumeUploader.jsx";
import CandidateTable, { CandidateToolbar, useVisibleCandidates } from "../components/CandidateTable.jsx";
import StatCard from "../components/StatCard.jsx";
import LoadingState from "../components/LoadingState.jsx";
import ErrorMessage from "../components/ErrorMessage.jsx";
import { useResults, EMPTY_JOB } from "../context/ResultsContext.jsx";
import { analyzeResumes, exportCsv, extractErrorMessage, getConfig } from "../services/api.js";
import { downloadBlob, fmtScore } from "../utils/format.js";

const FALLBACK_CONFIG = {
  max_file_size_mb: 5,
  max_files_per_request: 25,
  min_job_description_chars: 20,
  max_job_description_chars: 20000,
};

let nextId = 1;
const newId = () => `f${nextId++}`;

export default function Dashboard() {
  const navigate = useNavigate();
  const { result, job, setJob, items, setItems, view, setView, setAnalysis, clearAll } = useResults();
  const [config, setConfig] = useState(FALLBACK_CONFIG);
  const [phase, setPhase] = useState("idle"); // idle | uploading | analyzing
  const [progress, setProgress] = useState(null);
  const [error, setError] = useState(null);
  const [formErrors, setFormErrors] = useState({});
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState(null);

  useEffect(() => {
    getConfig().then(setConfig).catch(() => { /* defaults are fine; the navbar shows backend status */ });
  }, []);

  const busy = phase !== "idle";
  const sendable = items.filter((i) => !i.rejected);

  // ---- files -----------------------------------------------------------
  const addFiles = (list) => {
    setError(null);
    setItems((current) => {
      const next = [...current];
      list.forEach((file) => {
        const dup = next.some((i) => i.file.name === file.name && i.file.size === file.size && i.file.lastModified === file.lastModified);
        if (dup) return;
        const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
        let rejected = null;
        if (![".pdf", ".docx"].includes(ext)) rejected = ext === ".doc" ? "Legacy .doc is not supported. Save as .docx or PDF." : "Unsupported file type. Use PDF or DOCX.";
        else if (file.size === 0) rejected = "The file is empty.";
        else if (file.size > config.max_file_size_mb * 1024 * 1024) rejected = `Larger than the ${config.max_file_size_mb} MB limit.`;
        else if (next.filter((i) => !i.rejected).length >= config.max_files_per_request) rejected = `Only ${config.max_files_per_request} resumes can be analysed at once.`;
        next.push({
          id: newId(), file, rejected: !!rejected,
          status: rejected ? "failed" : "ready", message: rejected || "", warnings: [],
        });
      });
      return next;
    });
  };

  const removeFile = (id) => setItems((cur) => cur.filter((i) => i.id !== id));

  // ---- analysis --------------------------------------------------------
  const validate = () => {
    const errs = {};
    if (!job.jobTitle.trim()) errs.jobTitle = "Enter a job title.";
    if (!job.jobDescription.trim()) errs.jobDescription = "Paste a job description.";
    else if (job.jobDescription.trim().length < config.min_job_description_chars)
      errs.jobDescription = `The description must be at least ${config.min_job_description_chars} characters.`;
    setFormErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const analyze = async () => {
    setError(null);
    setExportError(null);
    if (!validate()) return;
    if (sendable.length === 0) {
      setError({ title: "No resumes to analyse", message: "Add at least one PDF or DOCX resume." });
      return;
    }
    const sent = sendable;
    const setStatus = (status) =>
      setItems((cur) => cur.map((i) => (sent.some((s) => s.id === i.id) ? { ...i, status, message: "", warnings: [] } : i)));
    setStatus("uploading");
    setPhase("uploading");
    setProgress(0);
    try {
      const data = await analyzeResumes({
        job: {
          jobTitle: job.jobTitle.trim(),
          jobDescription: job.jobDescription.trim(),
          requiredSkills: job.requiredSkills,
          preferredSkills: job.preferredSkills,
          minExperienceYears: job.minExperienceYears,
          educationRequirement: job.educationRequirement.trim(),
        },
        files: sent.map((s) => s.file),
        onUploadProgress: (e) => {
          if (!e.total) return;
          const pct = Math.round((e.loaded / e.total) * 100);
          setProgress(pct);
          if (pct >= 100) { setPhase("analyzing"); setStatus("analyzing"); }
        },
      });
      const outcome = new Map();
      data.candidates.forEach((c) => outcome.set(c.upload_index, { status: c.warnings.length ? "warning" : "processed", message: "", warnings: c.warnings }));
      data.errors.forEach((e) => outcome.set(e.upload_index, { status: "failed", message: e.message, warnings: [] }));
      setItems((cur) => cur.map((i) => {
        const idx = sent.findIndex((s) => s.id === i.id);
        return idx === -1 ? i : { ...i, ...(outcome.get(idx) || { status: "failed", message: "No result returned." }) };
      }));
      setAnalysis(data, sent.map((s) => s.file));
    } catch (err) {
      setStatus("ready");
      setError({ title: "Analysis could not be completed", message: await extractErrorMessage(err) });
    } finally {
      setPhase("idle");
      setProgress(null);
    }
  };

  const startOver = () => {
    clearAll();
    setJob(EMPTY_JOB);
    setFormErrors({});
    setError(null);
  };

  // ---- results ---------------------------------------------------------
  const candidates = result?.candidates ?? [];
  const rows = useVisibleCandidates(candidates, view);
  const hasJobSkills = (result?.job.required_skills.length ?? 0) + (result?.job.preferred_skills.length ?? 0) > 0;
  const warningFiles = useMemo(() => candidates.filter((c) => c.warnings.length).length, [candidates]);

  const doExport = async () => {
    setExporting(true);
    setExportError(null);
    try {
      const blob = await exportCsv({ candidates: rows, errors: result.errors });
      downloadBlob(blob, "resumeiq_results.csv");
    } catch (err) {
      setExportError(await extractErrorMessage(err));
    } finally {
      setExporting(false);
    }
  };

  return (
    <main className="page">
      <div className="page-head">
        <h1>Screen resumes against a job</h1>
        <p>
          Rank resumes by skill coverage and meaning similarity to your job description. Results are estimates to
          support your review, not hiring decisions.
        </p>
      </div>

      <div className="setup-grid">
        <section className="panel" aria-labelledby="step-job">
          <h2 id="step-job"><span className="step">1</span> Job requirements</h2>
          <JobDescriptionForm
            value={job}
            onChange={setJob}
            errors={formErrors}
            disabled={busy}
            minChars={config.min_job_description_chars}
            maxChars={config.max_job_description_chars}
          />
        </section>

        <section className="panel" aria-labelledby="step-resumes">
          <h2 id="step-resumes"><span className="step">2</span> Resumes</h2>
          <ResumeUploader
            items={items}
            onAdd={addFiles}
            onRemove={removeFile}
            busy={busy}
            uploadProgress={phase === "uploading" ? progress : null}
            maxFiles={config.max_files_per_request}
            maxSizeMb={config.max_file_size_mb}
          />
          <div className="actions">
            <button type="button" className="btn btn-primary" onClick={analyze} disabled={busy}>
              {busy ? <Loader2 size={16} className="spin" aria-hidden="true" /> : <Sparkles size={16} aria-hidden="true" />}
              {busy ? "Analyzing…" : "Analyze Resumes"}
            </button>
            <button type="button" className="btn btn-quiet" onClick={startOver} disabled={busy || (!items.length && !result)}>
              <RotateCcw size={14} aria-hidden="true" /> Start over
            </button>
          </div>
          <p className="hint">Resumes are processed in memory and are not stored by the server.</p>
        </section>
      </div>

      {phase === "uploading" && <LoadingState title="Uploading resumes" detail={`${progress ?? 0}% uploaded`} progress={progress ?? 0} />}
      {phase === "analyzing" && (
        <LoadingState title="Analyzing resumes" detail="Reading text, finding skills and comparing meaning. The first run can take longer while the model warms up." />
      )}
      {error && <ErrorMessage title={error.title}>{error.message}</ErrorMessage>}

      {!result && !busy && !error && (
        <div className="empty">
          <h2>No results yet</h2>
          <p>Enter a job description, add resumes and choose “Analyze Resumes”. Ranked candidates appear here.</p>
        </div>
      )}

      {result && (
        <section className="results" aria-labelledby="results-title">
          <div className="results-head">
            <div>
              <h2 id="results-title">Results for {result.job.job_title}</h2>
              <p className="hint">Model: {result.model_id} · Scoring v{result.scoring_version}</p>
            </div>
            <button type="button" className="btn btn-secondary" onClick={doExport} disabled={exporting || rows.length === 0}>
              {exporting ? <Loader2 size={16} className="spin" aria-hidden="true" /> : <Download size={16} aria-hidden="true" />}
              Export CSV
            </button>
          </div>

          {exportError && <ErrorMessage title="Export failed">{exportError}</ErrorMessage>}

          <div className="stats">
            <StatCard label="Resumes uploaded" value={result.summary.total_uploaded} tone="info" />
            <StatCard label="Processed successfully" value={result.summary.processed} tone="info" />
            <StatCard label="Failed" value={result.summary.failed} tone={result.summary.failed ? "bad" : "info"} />
            <StatCard label="Candidates with results" value={result.summary.candidates_with_results} tone="info" />
            <StatCard label="Average matching score" value={fmtScore(result.summary.average_score)} tone="info" hint="out of 100" />
          </div>

          <p className="disclaimer">{result.score_disclaimer}</p>

          {!hasJobSkills && candidates.length > 0 && (
            <ErrorMessage tone="warn" title="No skills were specified">
              Scores rely entirely on semantic similarity to the job description. Add required skills for a skill-coverage breakdown.
            </ErrorMessage>
          )}
          {warningFiles > 0 && (
            <ErrorMessage tone="warn" title={`${warningFiles} resume${warningFiles > 1 ? "s" : ""} processed with warnings`}>
              Open a candidate to read the warnings before relying on the result.
            </ErrorMessage>
          )}
          {result.errors.length > 0 && (
            <ErrorMessage title={`${result.errors.length} file${result.errors.length > 1 ? "s" : ""} could not be processed`}>
              <ul className="error-list">
                {result.errors.map((e) => (
                  <li key={`${e.upload_index}-${e.filename}`}><strong>{e.filename}</strong>: {e.message}</li>
                ))}
              </ul>
            </ErrorMessage>
          )}

          {candidates.length > 0 ? (
            <>
              <CandidateToolbar
                candidates={candidates}
                query={view.query}
                setQuery={(query) => setView({ ...view, query })}
                sortKey={view.sortKey}
                setSortKey={(sortKey) => setView({ ...view, sortKey })}
                skills={view.skills}
                setSkills={(skills) => setView({ ...view, skills })}
                shown={rows.length}
              />
              <CandidateTable rows={rows} hasJobSkills={hasJobSkills} onOpen={(c) => navigate(`/candidates/${c.resume_id}`)} />
            </>
          ) : (
            <div className="empty compact">
              <p><strong>No resume could be processed.</strong></p>
              <p className="hint">Fix the files listed above and analyse again.</p>
            </div>
          )}
        </section>
      )}
    </main>
  );
}

import SkillInput from "./SkillInput.jsx";

export default function JobDescriptionForm({ value, onChange, errors, disabled, minChars = 20, maxChars = 20000 }) {
  const set = (key) => (e) => onChange({ ...value, [key]: e.target.value });
  return (
    <fieldset className="form" disabled={disabled}>
      <legend className="sr-only">Job requirements</legend>

      <div className="field">
        <label htmlFor="jobTitle">Job title</label>
        <input
          id="jobTitle"
          value={value.jobTitle}
          onChange={set("jobTitle")}
          placeholder="e.g. Machine Learning Engineer"
          maxLength={200}
          aria-invalid={!!errors.jobTitle}
          aria-describedby={errors.jobTitle ? "jobTitle-err" : undefined}
        />
        {errors.jobTitle && <p className="field-error" id="jobTitle-err">{errors.jobTitle}</p>}
      </div>

      <div className="field">
        <label htmlFor="jobDescription">Job description</label>
        <textarea
          id="jobDescription"
          rows={9}
          value={value.jobDescription}
          onChange={set("jobDescription")}
          placeholder="Paste the full job description: responsibilities, qualifications, tools."
          maxLength={maxChars}
          aria-invalid={!!errors.jobDescription}
          aria-describedby="jobDescription-hint"
        />
        <p className={errors.jobDescription ? "field-error" : "hint"} id="jobDescription-hint">
          {errors.jobDescription || `At least ${minChars} characters. The text is compared to each resume by meaning.`}
        </p>
      </div>

      <div className="two-col">
        <SkillInput
          label="Required skills"
          value={value.requiredSkills}
          onChange={(requiredSkills) => onChange({ ...value, requiredSkills })}
          placeholder="Python, Docker…"
          hint="Press Enter or comma to add. Aliases like k8s are recognised."
        />
        <SkillInput
          label="Preferred skills (optional)"
          value={value.preferredSkills}
          onChange={(preferredSkills) => onChange({ ...value, preferredSkills })}
          placeholder="Airflow, AWS…"
          hint="Nice-to-have skills carry less weight."
        />
      </div>

      <div className="two-col">
        <div className="field">
          <label htmlFor="minExp">Minimum experience in years (optional)</label>
          <input
            id="minExp"
            type="number"
            min="0"
            max="60"
            step="0.5"
            inputMode="decimal"
            value={value.minExperienceYears}
            onChange={set("minExperienceYears")}
            aria-describedby="minExp-hint"
          />
          <p className="hint" id="minExp-hint">Shown beside each result for review; it does not change the score.</p>
        </div>
        <div className="field">
          <label htmlFor="education">Education requirement (optional)</label>
          <input
            id="education"
            value={value.educationRequirement}
            onChange={set("educationRequirement")}
            maxLength={300}
            placeholder="e.g. Bachelor's in a related field"
            aria-describedby="education-hint"
          />
          <p className="hint" id="education-hint">Recorded with the job. Education is not evaluated automatically.</p>
        </div>
      </div>
    </fieldset>
  );
}

import axios from "axios";

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

const client = axios.create({ baseURL: API_BASE_URL });

/** Turn any axios failure into a message a recruiter can act on. */
export async function extractErrorMessage(err) {
  if (err?.response) {
    let data = err.response.data;
    if (data instanceof Blob) {
      try {
        data = JSON.parse(await data.text());
      } catch {
        data = null;
      }
    }
    if (data?.error?.message) return data.error.message;
    if (err.response.status === 413) return "The upload is too large. Reduce the number or size of files.";
    return `The server returned an error (HTTP ${err.response.status}).`;
  }
  if (err?.code === "ERR_NETWORK" || err?.request) {
    return `Cannot reach the ResumeIQ backend at ${API_BASE_URL}. Check that it is running and that CORS_ORIGINS allows this page.`;
  }
  return err?.message || "Something went wrong.";
}

export async function getHealth() {
  const { data } = await client.get("/health", { timeout: 8000 });
  return data;
}

export async function getConfig() {
  const { data } = await client.get("/api/v1/config", { timeout: 8000 });
  return data;
}

/** job: { jobTitle, jobDescription, requiredSkills[], preferredSkills[], minExperienceYears, educationRequirement } */
export async function analyzeResumes({ job, files, onUploadProgress }) {
  const form = new FormData();
  form.append("job_title", job.jobTitle);
  form.append("job_description", job.jobDescription);
  form.append("required_skills", JSON.stringify(job.requiredSkills));
  form.append("preferred_skills", JSON.stringify(job.preferredSkills));
  if (job.minExperienceYears !== "" && job.minExperienceYears != null) {
    form.append("min_experience_years", String(job.minExperienceYears));
  }
  if (job.educationRequirement) form.append("education_requirement", job.educationRequirement);
  files.forEach((file) => form.append("resumes", file, file.name));
  const { data } = await client.post("/api/v1/match", form, { onUploadProgress, timeout: 0 });
  return data;
}

/** Sends the rows to export; the server stores nothing. Returns a Blob. */
export async function exportCsv({ candidates, errors }) {
  const { data } = await client.post(
    "/api/v1/export/csv",
    { candidates, errors },
    { responseType: "blob", timeout: 60000 }
  );
  return data;
}

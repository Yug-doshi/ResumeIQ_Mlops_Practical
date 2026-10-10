# ResumeIQ frontend

React + Vite + Axios + React Router + Lucide icons, plain CSS (design tokens in `src/styles/index.css`).

```powershell
cd frontend
Copy-Item .env.example .env   # set VITE_API_BASE_URL if the backend is not on http://localhost:8000
npm install
npm run dev                   # http://localhost:5173
npm run build                 # production build into dist/
```

Structure: `pages/` (Dashboard, CandidateDetails), `components/`, `services/api.js` (all HTTP calls),
`context/ResultsContext.jsx` (in-memory session state — nothing is written to browser storage).
Full setup, API and security notes are in the repository README.

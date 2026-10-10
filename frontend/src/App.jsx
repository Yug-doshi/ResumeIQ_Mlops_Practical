import { Link, Route, Routes } from "react-router-dom";
import Navbar from "./components/Navbar.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import CandidateDetails from "./pages/CandidateDetails.jsx";

function NotFound() {
  return (
    <main className="page">
      <div className="empty">
        <h1>Page not found</h1>
        <p>The page you opened does not exist.</p>
        <Link className="btn btn-primary" to="/">Back to dashboard</Link>
      </div>
    </main>
  );
}

export default function App() {
  return (
    <>
      <a className="skip-link" href="#main">Skip to content</a>
      <Navbar />
      <div id="main">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/candidates/:resumeId" element={<CandidateDetails />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </div>
    </>
  );
}

import { useEffect, useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { ScanSearch } from "lucide-react";
import { getHealth } from "../services/api.js";

function useBackendStatus() {
  const [state, setState] = useState({ tone: "info", label: "Checking backend…" });
  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      try {
        const h = await getHealth();
        if (cancelled) return;
        if (h.ready) setState({ tone: "good", label: "Model ready" });
        else if (h.model.status === "loading") setState({ tone: "info", label: "Model loading…" });
        else setState({ tone: "warn", label: "Model not ready" });
      } catch {
        if (!cancelled) setState({ tone: "bad", label: "Backend offline" });
      }
    };
    check();
    const id = setInterval(check, 15000);
    window.addEventListener("focus", check);
    return () => {
      cancelled = true;
      clearInterval(id);
      window.removeEventListener("focus", check);
    };
  }, []);
  return state;
}

export default function Navbar() {
  const status = useBackendStatus();
  return (
    <header className="navbar">
      <div className="navbar-inner">
        <Link to="/" className="brand" aria-label="ResumeIQ home">
          <ScanSearch size={22} aria-hidden="true" />
          <span>ResumeIQ</span>
        </Link>
        <nav aria-label="Main">
          <NavLink to="/" end className="nav-link">Dashboard</NavLink>
        </nav>
        <span className={`status-pill tone-${status.tone}`} role="status">
          <span className="dot" aria-hidden="true" />
          {status.label}
        </span>
      </div>
    </header>
  );
}

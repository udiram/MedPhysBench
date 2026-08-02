import { ExternalLink, Menu, X } from "lucide-react";
import { Logo } from "../Logo";

type HeaderProps = {
  mobileOpen: boolean;
  onToggle: () => void;
  onClose: () => void;
  repoUrl: string;
};

export function Header({ mobileOpen, onToggle, onClose, repoUrl }: HeaderProps) {
  return (
    <header className="topbar">
      <a href="#top" aria-label="MedPhysBench home" onClick={onClose}>
        <Logo />
      </a>
      <button
        className="menu-button"
        aria-label="Toggle navigation"
        aria-expanded={mobileOpen}
        onClick={onToggle}
      >
        {mobileOpen ? <X /> : <Menu />}
      </button>
      <nav className={mobileOpen ? "nav-links nav-open" : "nav-links"} aria-label="Primary">
        <a href="#benchmark" onClick={onClose}>Benchmark</a>
        <a href="#fleet" onClick={onClose}>Models</a>
        <a href="#methodology" onClick={onClose}>Methods</a>
        <a href="#coverage" onClick={onClose}>Tasks</a>
        <a href="#leaderboard" onClick={onClose}>Results</a>
        <a href="#governance" onClick={onClose}>About</a>
        <a href={repoUrl} target="_blank" rel="noreferrer" onClick={onClose}>
          GitHub
          <ExternalLink aria-hidden="true" />
        </a>
      </nav>
    </header>
  );
}

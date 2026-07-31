import { ExternalLink, Github, Menu, X } from "lucide-react";
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
        <a href="#leaderboard" onClick={onClose}>Leaderboard</a>
        <a href="#coverage" onClick={onClose}>Coverage</a>
        <a href="#methodology" onClick={onClose}>Methodology</a>
        <a href="#governance" onClick={onClose}>Governance</a>
        <a href="#integrity" onClick={onClose}>Integrity</a>
        <a href={`${repoUrl}/tree/main/docs`} target="_blank" rel="noreferrer" onClick={onClose}>
          Docs
          <ExternalLink aria-hidden="true" />
        </a>
        <a href={repoUrl} target="_blank" rel="noreferrer" onClick={onClose}>
          <Github aria-hidden="true" />
          GitHub
        </a>
      </nav>
    </header>
  );
}

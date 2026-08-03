import { ExternalLink, Menu, X } from "lucide-react";
import { useEffect, useRef } from "react";
import { Logo } from "../Logo";

type HeaderProps = {
  mobileOpen: boolean;
  onToggle: () => void;
  onClose: () => void;
  repoUrl: string;
};

export function Header({ mobileOpen, onToggle, onClose, repoUrl }: HeaderProps) {
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const navRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!mobileOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const firstLink = navRef.current?.querySelector<HTMLAnchorElement>("a");
    firstLink?.focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      onClose();
      menuButtonRef.current?.focus();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [mobileOpen, onClose]);

  return (
    <header className="topbar">
      <a href="#top" aria-label="MedPhysBench home" onClick={onClose}>
        <Logo />
      </a>
      <button
        ref={menuButtonRef}
        className="menu-button"
        aria-label="Toggle navigation"
        aria-expanded={mobileOpen}
        aria-controls="primary-navigation"
        onClick={onToggle}
      >
        {mobileOpen ? <X /> : <Menu />}
      </button>
      {mobileOpen ? (
        <button
          type="button"
          className="nav-backdrop"
          aria-label="Close navigation"
          onClick={() => {
            onClose();
            menuButtonRef.current?.focus();
          }}
        />
      ) : null}
      <nav
        ref={navRef}
        id="primary-navigation"
        className={mobileOpen ? "nav-links nav-open" : "nav-links"}
        aria-label="Primary"
      >
        <a href="#benchmark" onClick={onClose}>Benchmark</a>
        <a href="#model-index" onClick={onClose}>Models</a>
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

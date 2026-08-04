import { ExternalLink, Menu, X } from "lucide-react";
import { useEffect, useRef } from "react";
import { Logo } from "../Logo";

type HeaderProps = {
  currentPage: "overview" | "results" | "evals" | "explore" | "humans" | "run" | "methods";
  mobileOpen: boolean;
  onToggle: () => void;
  onClose: () => void;
  repoUrl: string;
};

export function Header({ currentPage, mobileOpen, onToggle, onClose, repoUrl }: HeaderProps) {
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const navRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!mobileOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const firstLink = navRef.current?.querySelector<HTMLAnchorElement>("a");
    firstLink?.focus();

    const main = document.getElementById("main-content");
    if (main) main.inert = true;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
        menuButtonRef.current?.focus();
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = [
        menuButtonRef.current,
        ...Array.from(navRef.current?.querySelectorAll<HTMLAnchorElement>("a") ?? []),
      ].filter((item): item is HTMLButtonElement | HTMLAnchorElement => item !== null);
      const first = focusable[0];
      const last = focusable.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      if (main) main.inert = false;
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [mobileOpen, onClose]);

  return (
    <header className="topbar">
      <a href="/" aria-label="MedPhysBench home" onClick={onClose}>
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
        <a href="/" aria-current={currentPage === "overview" ? "page" : undefined} onClick={onClose}>Overview</a>
        <a href="/results" aria-current={currentPage === "results" ? "page" : undefined} onClick={onClose}>Leaderboard</a>
        <a href="/evals" aria-current={currentPage === "evals" ? "page" : undefined} onClick={onClose}>Evals</a>
        <a href="/explore" aria-current={currentPage === "explore" ? "page" : undefined} onClick={onClose}>Compare</a>
        <a href="/humans" aria-current={currentPage === "humans" ? "page" : undefined} onClick={onClose}>Human benchmark</a>
        <a href="/run" aria-current={currentPage === "run" ? "page" : undefined} onClick={onClose}>Run or request</a>
        <a href={repoUrl} target="_blank" rel="noreferrer" onClick={onClose}>
          GitHub
          <ExternalLink aria-hidden="true" />
        </a>
      </nav>
    </header>
  );
}

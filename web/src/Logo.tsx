export function Logo() {
  return (
    <span className="brand">
      <svg aria-hidden="true" className="brand-mark" viewBox="0 0 40 40">
        <path d="M20 2.5 35.2 11v18L20 37.5 4.8 29V11L20 2.5Z" />
        <path d="M20 8v24M9.5 14l21 12M30.5 14l-21 12" />
        <circle cx="20" cy="20" r="4.1" />
      </svg>
      <span>MedPhysBench</span>
    </span>
  );
}

/** Geometric mark for AB Logistics OS (SVG). */
export function AbLogoMark({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden
    >
      <rect x="1" y="1" width="30" height="30" rx="8" className="fill-zinc-900 stroke-zinc-700" strokeWidth="1" />
      <path
        d="M8 22V10l8-5 8 5v12"
        className="stroke-emerald-500"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
      <path d="M16 5v22" className="stroke-zinc-600" strokeWidth="1" strokeLinecap="round" opacity="0.45" />
    </svg>
  );
}

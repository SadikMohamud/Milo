// The paw from the logo, redrawn as a vector so it scales cleanly.
export function Paw({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 100 100" aria-hidden="true" focusable="false">
      <g fill="currentColor">
        <ellipse cx="22" cy="40" rx="9" ry="12.5" transform="rotate(-22 22 40)" />
        <ellipse cx="39" cy="22" rx="9.5" ry="13.5" transform="rotate(-8 39 22)" />
        <ellipse cx="61" cy="22" rx="9.5" ry="13.5" transform="rotate(8 61 22)" />
        <ellipse cx="78" cy="40" rx="9" ry="12.5" transform="rotate(22 78 40)" />
        <path d="M50 46c-11 0-17 9-23 18-5 7-9 12-7 19 2 8 11 10 18 8 5-1 8-3 12-3s7 2 12 3c7 2 16 0 18-8 2-7-2-12-7-19-6-9-12-18-23-18z" />
      </g>
    </svg>
  );
}

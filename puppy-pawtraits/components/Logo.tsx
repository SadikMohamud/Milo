// The full Puppy Pawtraits logo as a mask, so it takes the colour of the surrounding text.
export function Logo({ className }: { className?: string }) {
  return <span className={`logo-mark ${className ?? ''}`} aria-hidden="true" />;
}

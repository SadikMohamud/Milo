'use client';

import { useEffect, useRef, type ReactNode } from 'react';
import { onScrollFrame, prefersReducedMotion } from './shared/motion';

export interface ParallaxProps {
  children: ReactNode;
  /** Positive values move slower than the page, negative values faster. 0.2 is a gentle layer. */
  speed?: number;
  className?: string;
}

// Moves a layer at a different rate to the page, measured from the centre of the viewport.
export function Parallax({ children, speed = 0.2, className }: ParallaxProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || prefersReducedMotion()) return;
    return onScrollFrame(() => {
      const parent = el.parentElement ?? el;
      const rect = parent.getBoundingClientRect();
      const offset = rect.top + rect.height / 2 - window.innerHeight / 2;
      el.style.transform = `translate3d(0, ${(offset * speed).toFixed(2)}px, 0)`;
    });
  }, [speed]);

  return <div ref={ref} className={className} style={{ willChange: 'transform' }}>{children}</div>;
}

'use client';

import { createElement, useEffect, useRef } from 'react';
import { prefersReducedMotion } from './shared/motion';

export interface SplitTextProps {
  children: string;
  by?: 'words' | 'chars';
  /** Delay between pieces, in milliseconds. */
  interval?: number;
  duration?: number;
  easing?: string;
  rootMargin?: string;
  as?: 'h1' | 'h2' | 'h3' | 'p' | 'span';
  className?: string;
}

// Splits a line into words or characters and lifts them into place in sequence. Screen readers get the whole line.
export function SplitText({
  children, by = 'words', interval = 40, duration = 800, easing = 'cubic-bezier(0.16, 1, 0.3, 1)',
  rootMargin = '0px 0px -10% 0px', as = 'h2', className,
}: SplitTextProps) {
  const ref = useRef<HTMLElement>(null);
  const pieces = by === 'chars' ? Array.from(children) : children.split(/(\s+)/);

  useEffect(() => {
    const root = ref.current;
    if (!root || prefersReducedMotion()) return;
    const spans = Array.from(root.querySelectorAll<HTMLElement>('[data-piece]'));
    for (const span of spans) {
      span.style.opacity = '0';
      span.style.transform = 'translate3d(0, 0.6em, 0)';
    }
    const observer = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return;
      spans.forEach((span, i) => {
        span.style.transition = `opacity ${duration}ms ${easing} ${i * interval}ms, transform ${duration}ms ${easing} ${i * interval}ms`;
        span.style.opacity = '1';
        span.style.transform = 'none';
      });
      observer.disconnect();
    }, { rootMargin });
    observer.observe(root);
    return () => observer.disconnect();
  }, [children, by, interval, duration, easing, rootMargin]);

  return createElement(
    as,
    { ref, className, 'aria-label': children },
    pieces.map((piece, i) =>
      /^\s+$/.test(piece)
        ? piece
        : <span key={i} data-piece="" aria-hidden="true" style={{ display: 'inline-block', whiteSpace: 'pre' }}>{piece}</span>,
    ),
  );
}

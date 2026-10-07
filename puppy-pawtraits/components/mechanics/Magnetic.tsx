'use client';

import { useEffect, useRef, type ReactNode } from 'react';
import { isCoarsePointer, prefersReducedMotion } from './shared/motion';

export interface MagneticProps {
  children: ReactNode;
  /** How far the element follows the pointer, as a share of the pointer's offset from its centre. */
  strength?: number;
  className?: string;
}

// Pulls an element towards the pointer while it hovers, then eases it back.
export function Magnetic({ children, strength = 0.3, className }: MagneticProps) {
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || prefersReducedMotion() || isCoarsePointer()) return;
    const move = (event: PointerEvent) => {
      const rect = el.getBoundingClientRect();
      const dx = (event.clientX - (rect.left + rect.width / 2)) * strength;
      const dy = (event.clientY - (rect.top + rect.height / 2)) * strength;
      el.style.transition = 'transform 120ms ease-out';
      el.style.transform = `translate3d(${dx.toFixed(1)}px, ${dy.toFixed(1)}px, 0)`;
    };
    const leave = () => {
      el.style.transition = 'transform 600ms cubic-bezier(0.22, 1, 0.36, 1)';
      el.style.transform = 'translate3d(0, 0, 0)';
    };
    el.addEventListener('pointermove', move);
    el.addEventListener('pointerleave', leave);
    return () => {
      el.removeEventListener('pointermove', move);
      el.removeEventListener('pointerleave', leave);
    };
  }, [strength]);

  return <span ref={ref} className={className} style={{ display: 'inline-block', willChange: 'transform' }}>{children}</span>;
}

'use client';

import { useEffect, useRef, type ReactNode } from 'react';
import { prefersReducedMotion } from './shared/motion';

export interface ScrollRevealProps {
  children: ReactNode;
  /** When to reveal, as an IntersectionObserver root margin. '0px 0px -20% 0px' reveals as the top reaches 80% of the viewport. */
  rootMargin?: string;
  duration?: number;
  easing?: string;
  /** Delay between children that enter together, in milliseconds. */
  stagger?: number;
  /** Starting offset in pixels. */
  distance?: number;
  once?: boolean;
  className?: string;
}

// Reveals each direct child once as it enters the viewport. Children entering together are staggered.
export function ScrollReveal({
  children, rootMargin = '0px 0px -15% 0px', duration = 700, easing = 'cubic-bezier(0.16, 1, 0.3, 1)',
  stagger = 0, distance = 24, once = true, className,
}: ScrollRevealProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const root = ref.current;
    if (!root || prefersReducedMotion()) return;
    const items = Array.from(root.children) as HTMLElement[];
    const hide = (el: HTMLElement) => {
      el.style.transition = 'none';
      el.style.opacity = '0';
      el.style.transform = `translate3d(0, ${distance}px, 0)`;
    };
    items.forEach(hide);

    const observer = new IntersectionObserver((entries) => {
      let batch = 0;
      for (const entry of entries) {
        const el = entry.target as HTMLElement;
        if (entry.isIntersecting) {
          const delay = batch++ * stagger;
          el.style.transition = `opacity ${duration}ms ${easing} ${delay}ms, transform ${duration}ms ${easing} ${delay}ms`;
          el.style.opacity = '1';
          el.style.transform = 'none';
          if (once) observer.unobserve(el);
        } else if (!once) {
          hide(el);
        }
      }
    }, { rootMargin });
    items.forEach((el) => observer.observe(el));

    return () => {
      observer.disconnect();
      for (const el of items) {
        el.style.removeProperty('transition');
        el.style.removeProperty('opacity');
        el.style.removeProperty('transform');
      }
    };
  }, [rootMargin, duration, easing, stagger, distance, once]);

  return <div ref={ref} className={className}>{children}</div>;
}

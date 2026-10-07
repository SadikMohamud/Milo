'use client';

import { useEffect, type ReactNode } from 'react';
import { isCoarsePointer, prefersReducedMotion } from './shared/motion';

export interface SmoothScrollProps {
  children: ReactNode;
  /** Share of the remaining distance covered each frame. Lower is heavier. */
  lerp?: number;
}

// Inertial wheel scrolling on the native scroll position, so sticky positioning, anchors and the scrollbar keep working.
// Touch devices and reduced motion keep ordinary scrolling.
export function SmoothScroll({ children, lerp = 0.1 }: SmoothScrollProps) {
  useEffect(() => {
    if (prefersReducedMotion() || isCoarsePointer()) return;
    let target = window.scrollY;
    let current = window.scrollY;
    let frame = 0;

    const max = () => document.documentElement.scrollHeight - window.innerHeight;
    const step = () => {
      current += (target - current) * lerp;
      if (Math.abs(target - current) < 0.5) current = target;
      window.scrollTo(0, current);
      frame = current === target ? 0 : requestAnimationFrame(step);
    };
    const onWheel = (event: WheelEvent) => {
      if (event.ctrlKey || event.defaultPrevented) return;
      // let nested scrollable areas handle their own wheel input
      for (let el = event.target as HTMLElement | null; el && el !== document.body; el = el.parentElement) {
        const style = getComputedStyle(el);
        if (/(auto|scroll)/.test(style.overflowY) && el.scrollHeight > el.clientHeight) return;
      }
      event.preventDefault();
      const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? window.innerHeight : 1;
      target = Math.min(max(), Math.max(0, target + event.deltaY * unit));
      if (!frame) frame = requestAnimationFrame(step);
    };
    const onScroll = () => {
      // keyboard, scrollbar and anchor jumps move the page to somewhere we did not put it; follow them rather than fight them
      if (Math.abs(window.scrollY - current) > 2) {
        cancelAnimationFrame(frame);
        frame = 0;
        target = current = window.scrollY;
      }
    };

    window.addEventListener('wheel', onWheel, { passive: false });
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener('wheel', onWheel);
      window.removeEventListener('scroll', onScroll);
    };
  }, [lerp]);

  return <>{children}</>;
}

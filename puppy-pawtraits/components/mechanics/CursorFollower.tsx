'use client';

import { useEffect, useRef } from 'react';
import { isCoarsePointer, prefersReducedMotion } from './shared/motion';

export interface CursorFollowerProps {
  size?: number;
  /** Share of the remaining distance covered each frame. Lower trails further behind. */
  lag?: number;
  /** Scale applied over links and buttons. */
  hoverScale?: number;
  className?: string;
}

// A small disc that trails the pointer and grows over interactive elements. The native cursor stays visible.
export function CursorFollower({ size = 14, lag = 0.2, hoverScale = 2.6, className }: CursorFollowerProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || prefersReducedMotion() || isCoarsePointer()) return;
    let x = -100, y = -100, tx = -100, ty = -100, scale = 1, targetScale = 1, frame = 0;

    const loop = () => {
      x += (tx - x) * lag;
      y += (ty - y) * lag;
      scale += (targetScale - scale) * 0.2;
      el.style.transform = `translate3d(${x - size / 2}px, ${y - size / 2}px, 0) scale(${scale.toFixed(3)})`;
      frame = requestAnimationFrame(loop);
    };
    const move = (event: PointerEvent) => {
      tx = event.clientX;
      ty = event.clientY;
      el.style.opacity = '1';
      targetScale = (event.target as Element | null)?.closest('a, button, [role="button"]') ? hoverScale : 1;
    };
    const leave = () => { el.style.opacity = '0'; };

    window.addEventListener('pointermove', move, { passive: true });
    document.documentElement.addEventListener('pointerleave', leave);
    frame = requestAnimationFrame(loop);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener('pointermove', move);
      document.documentElement.removeEventListener('pointerleave', leave);
    };
  }, [size, lag, hoverScale]);

  return (
    <div
      ref={ref}
      aria-hidden="true"
      className={className}
      style={{
        position: 'fixed', top: 0, left: 0, width: size, height: size, borderRadius: '50%', pointerEvents: 'none', zIndex: 9999,
        background: 'var(--colour-accent, currentColor)', mixBlendMode: 'difference', opacity: 0, transition: 'opacity 200ms ease',
      }}
    />
  );
}

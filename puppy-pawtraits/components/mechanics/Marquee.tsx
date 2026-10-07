'use client';

import { useEffect, useRef, type ReactNode } from 'react';
import { prefersReducedMotion } from './shared/motion';

export interface MarqueeProps {
  children: ReactNode;
  /** Pixels per second. */
  speed?: number;
  gap?: string;
  pauseOnHover?: boolean;
  reverse?: boolean;
  className?: string;
}

// A seamless horizontal loop: the content is rendered twice and the track moves by exactly half its width.
export function Marquee({ children, speed = 60, gap = '2rem', pauseOnHover = true, reverse = false, className }: MarqueeProps) {
  const track = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = track.current;
    if (!el || prefersReducedMotion()) return;
    let animation: Animation | null = null;
    const start = () => {
      animation?.cancel();
      const half = el.scrollWidth / 2;
      if (half <= 0) return;
      const frames = [{ transform: 'translate3d(0, 0, 0)' }, { transform: `translate3d(${-half}px, 0, 0)` }];
      animation = el.animate(reverse ? frames.reverse() : frames, { duration: (half / speed) * 1000, iterations: Infinity, easing: 'linear' });
    };
    start();
    const resize = new ResizeObserver(start);
    resize.observe(el);
    const pause = () => pauseOnHover && animation?.pause();
    const play = () => animation?.play();
    el.addEventListener('pointerenter', pause);
    el.addEventListener('pointerleave', play);
    return () => {
      resize.disconnect();
      animation?.cancel();
      el.removeEventListener('pointerenter', pause);
      el.removeEventListener('pointerleave', play);
    };
  }, [speed, pauseOnHover, reverse]);

  const group = { display: 'flex', gap, paddingRight: gap, flexShrink: 0 } as const;
  return (
    <div className={className} style={{ overflow: 'hidden' }}>
      <div ref={track} style={{ display: 'flex', width: 'max-content', willChange: 'transform' }}>
        <div style={group}>{children}</div>
        <div style={group} aria-hidden="true">{children}</div>
      </div>
    </div>
  );
}

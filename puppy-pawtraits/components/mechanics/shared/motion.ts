import { useEffect, useState, type RefObject } from 'react';

export const clamp = (value: number, min = 0, max = 1) => Math.min(max, Math.max(min, value));

// Reduced motion is respected everywhere: mechanics settle into their end state instead of animating.
export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReduced(query.matches);
    update();
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, []);
  return reduced;
}

export function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

export function isCoarsePointer(): boolean {
  return typeof window !== 'undefined' && window.matchMedia('(pointer: coarse)').matches;
}

// Progress of an element through the viewport: 0 as its top enters from below, 1 as its bottom leaves at the top.
export function viewportProgress(element: Element): number {
  const rect = element.getBoundingClientRect();
  const vh = window.innerHeight;
  return clamp((vh - rect.top) / (vh + rect.height));
}

// Runs `frame` on scroll and resize, at most once per animation frame.
export function onScrollFrame(frame: () => void): () => void {
  let queued = false;
  const tick = () => {
    queued = false;
    frame();
  };
  const request = () => {
    if (!queued) {
      queued = true;
      requestAnimationFrame(tick);
    }
  };
  window.addEventListener('scroll', request, { passive: true });
  window.addEventListener('resize', request);
  request();
  return () => {
    window.removeEventListener('scroll', request);
    window.removeEventListener('resize', request);
  };
}

export function useInView(ref: RefObject<Element | null>, rootMargin = '0px', once = true): boolean {
  const [inView, setInView] = useState(false);
  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        setInView(true);
        if (once) observer.disconnect();
      } else if (!once) {
        setInView(false);
      }
    }, { rootMargin });
    observer.observe(element);
    return () => observer.disconnect();
  }, [ref, rootMargin, once]);
  return inView;
}

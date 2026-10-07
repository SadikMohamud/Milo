'use client';

import { useEffect, useRef, useState } from 'react';
import { works, type Category } from '@/lib/catalogue';
import { ScrollReveal } from './mechanics/ScrollReveal';
import { SplitText } from './mechanics/SplitText';
import { Plate } from './Plate';

const filters: Array<'All' | Category> = ['All', 'Studio', 'Outdoor', 'Puppies'];

export function Work() {
  const [filter, setFilter] = useState<(typeof filters)[number]>('All');
  const [active, setActive] = useState<number | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);

  const shown = filter === 'All' ? works : works.filter((w) => w.category === filter);
  const current = active === null ? null : shown[active];

  useEffect(() => {
    const el = dialog.current;
    if (!el) return;
    if (current && !el.open) el.showModal();
    if (!current && el.open) el.close();
  }, [current]);

  useEffect(() => {
    if (active === null) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'ArrowRight') setActive((i) => (i === null ? i : (i + 1) % shown.length));
      if (event.key === 'ArrowLeft') setActive((i) => (i === null ? i : (i - 1 + shown.length) % shown.length));
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [active, shown.length]);

  return (
    <section className="work" id="work" aria-label="Selected work">
      <header className="section-head">
        <p className="eyebrow"><span className="eyebrow__num">01</span> Selected work</p>
        <SplitText as="h2" by="words" className="section-title" interval={60}>
          Every dog sits differently.
        </SplitText>
        <p className="section-lede">
          Studio portraits with nowhere to hide, long walks with the light behind them, and the
          first weeks of puppies who will never be this small again.
        </p>
      </header>

      <div className="filters" role="toolbar" aria-label="Filter the work">
        {filters.map((f) => (
          <button key={f} className="filter" aria-pressed={filter === f} onClick={() => { setFilter(f); setActive(null); }}>
            {f}
            <sup>{f === 'All' ? works.length : works.filter((w) => w.category === f).length}</sup>
          </button>
        ))}
      </div>

      <ScrollReveal key={filter} className="gallery" stagger={90} distance={48} duration={900}>
        {shown.map((work, i) => (
          <figure key={work.id} className={`gallery__item gallery__item--${work.shape}`}>
            <button className="gallery__open" onClick={() => setActive(i)} aria-label={`View ${work.name}, ${work.breed}`}>
              <span className="gallery__media">
                <Plate work={work} sizes="(max-width: 640px) 100vw, (max-width: 1100px) 50vw, 33vw" compact />
              </span>
            </button>
            <figcaption className="gallery__caption">
              <span className="gallery__num">{String(works.indexOf(work) + 1).padStart(2, '0')}</span>
              <span className="gallery__name">{work.name}</span>
              <span className="gallery__breed">{work.breed}</span>
            </figcaption>
          </figure>
        ))}
      </ScrollReveal>

      <dialog ref={dialog} className="lightbox" onClose={() => setActive(null)} onClick={(e) => e.target === e.currentTarget && setActive(null)}>
        {current && (
          <div className="lightbox__inner">
            <div className="lightbox__media">
              <Plate work={current} sizes="90vw" />
            </div>
            <div className="lightbox__bar">
              <p>
                <span className="lightbox__name">{current.name}</span>
                <span className="lightbox__breed">{current.breed}, {current.category}</span>
              </p>
              <div className="lightbox__nav">
                <button onClick={() => setActive((i) => (i! - 1 + shown.length) % shown.length)} aria-label="Previous portrait">Prev</button>
                <span>{String((active ?? 0) + 1).padStart(2, '0')} / {String(shown.length).padStart(2, '0')}</span>
                <button onClick={() => setActive((i) => (i! + 1) % shown.length)} aria-label="Next portrait">Next</button>
                <button onClick={() => setActive(null)} className="lightbox__close">Close</button>
              </div>
            </div>
          </div>
        )}
      </dialog>
    </section>
  );
}

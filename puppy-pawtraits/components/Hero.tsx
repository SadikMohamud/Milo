import Image from 'next/image';
import { findWork } from '@/lib/catalogue';
import { site } from '@/lib/site';
import { Magnetic } from './mechanics/Magnetic';
import { Marquee } from './mechanics/Marquee';
import { Parallax } from './mechanics/Parallax';
import { SplitText } from './mechanics/SplitText';
import { Paw } from './Paw';
import { Plate } from './Plate';

const stack = [
  { id: 'mabel', speed: -0.12, className: 'hero__plate hero__plate--a' },
  { id: 'biscuit', speed: 0.08, className: 'hero__plate hero__plate--b' },
  { id: 'scout', speed: 0.22, className: 'hero__plate hero__plate--c' },
];

const services = ['Studio sessions', 'Outdoor sessions', 'Fine art prints', 'Commissions', 'Puppy firsts'];

export function Hero() {
  return (
    <section className="hero" id="top">
      <div className="hero__grid">
        <div className="hero__copy">
          <p className="eyebrow hero__eyebrow">
            <span>Dog portrait photography</span>
            <span>by {site.photographer}</span>
          </p>

          <h1 className="hero__logo">
            <span className="sr-only">{site.name}</span>
            <Image src="/brand/logo-ink.png" alt="" width={1502} height={951} priority sizes="(max-width: 860px) 88vw, 46vw" />
          </h1>

          <SplitText as="p" by="words" interval={55} className="hero__line">
            Portraits of the ones who wait by the door.
          </SplitText>

          <div className="hero__ctas">
            <Magnetic strength={0.2}>
              <a href="#work" className="button button--ink">See the work</a>
            </Magnetic>
            <Magnetic strength={0.2}>
              <a href="#prints" className="button button--line">Shop prints</a>
            </Magnetic>
          </div>
        </div>

        <div className="hero__stack" aria-hidden="true">
          {stack.map(({ id, speed, className }, i) => (
            <Parallax key={id} speed={speed} className={className}>
              <div className="hero__frame" style={{ animationDelay: `${300 + i * 140}ms` }}>
                <Plate work={findWork(id)!} sizes="(max-width: 860px) 50vw, 24vw" priority={i === 0} />
              </div>
            </Parallax>
          ))}
        </div>
      </div>

      <a href="#work" className="hero__cue" aria-label="Scroll to the work">
        <span>Scroll</span>
        <span className="hero__cue-line" />
      </a>

      <Marquee speed={45} gap="2.5rem" className="band">
        {services.map((s) => (
          <span key={s} className="band__item">
            {s}
            <Paw className="band__paw" />
          </span>
        ))}
      </Marquee>
    </section>
  );
}

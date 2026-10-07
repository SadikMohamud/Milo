import Image from 'next/image';
import { site } from '@/lib/site';
import { Magnetic } from './mechanics/Magnetic';
import { ScrollReveal } from './mechanics/ScrollReveal';
import { SplitText } from './mechanics/SplitText';

const steps = [
  { title: 'Say hello', body: 'Tell Jason about your dog: name, age, quirks, the thing they do that nobody else understands.' },
  { title: 'The session', body: 'An unhurried hour in the studio or somewhere they love to walk. Treats encouraged, perfect behaviour not required.' },
  { title: 'Your gallery', body: 'A private online gallery within two weeks, ready to choose favourites for prints or digital files.' },
];

export function Commission() {
  const year = new Date().getFullYear();
  return (
    <footer className="commission" id="commission">
      <header className="section-head">
        <p className="eyebrow"><span className="eyebrow__num">03</span> Commission a portrait</p>
        <SplitText as="h2" by="words" className="section-title" interval={60}>
          Bring them in. Bring the treats.
        </SplitText>
      </header>

      <ScrollReveal className="steps" stagger={110}>
        {steps.map((step, i) => (
          <div key={step.title} className="step">
            <span className="step__num">{String(i + 1).padStart(2, '0')}</span>
            <h3 className="step__title">{step.title}</h3>
            <p>{step.body}</p>
          </div>
        ))}
      </ScrollReveal>

      <div className="contact">
        <Magnetic strength={0.12}>
          <a className="contact__mail" href={`mailto:${site.email}?subject=Portrait%20session`}>
            {site.email}
          </a>
        </Magnetic>
      </div>

      <div className="footer">
        <Image src="/brand/logo-ink.png" alt={site.name} width={1502} height={951} className="footer__logo" sizes="160px" />
        <p>© {year} {site.name}, {site.photographer}</p>
        <a href={site.instagram} target="_blank" rel="noreferrer">Instagram</a>
        <a href="#top">Back to top</a>
      </div>
    </footer>
  );
}

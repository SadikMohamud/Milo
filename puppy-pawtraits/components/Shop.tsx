'use client';

import { useState } from 'react';
import { findWork, formatPrice, prints, sizes, type Print } from '@/lib/catalogue';
import { useCart } from './Cart';
import { ScrollReveal } from './mechanics/ScrollReveal';
import { SplitText } from './mechanics/SplitText';
import { Plate } from './Plate';

function PrintCard({ print, index }: { print: Print; index: number }) {
  const { add } = useCart();
  const [sizeId, setSizeId] = useState(sizes[0].id);
  const size = sizes.find((s) => s.id === sizeId)!;
  const work = findWork(print.workId)!;

  return (
    <article className="print">
      <div className="print__frame">
        <div className="print__mat">
          <Plate work={work} sizes="(max-width: 640px) 90vw, (max-width: 1100px) 45vw, 30vw" />
        </div>
        <span className="print__edition">{print.edition}</span>
      </div>

      <div className="print__body">
        <div className="print__row">
          <h3 className="print__title">
            <span className="print__num">{String(index + 1).padStart(2, '0')}</span>
            {print.title}
          </h3>
          <p className="print__price" aria-live="polite">{formatPrice(size.price)}</p>
        </div>
        <p className="print__paper">{print.paper}</p>

        <fieldset className="sizes">
          <legend className="sr-only">Size for {print.title}</legend>
          {sizes.map((s) => (
            <label key={s.id} className="size" data-checked={s.id === sizeId}>
              <input type="radio" name={`size-${print.id}`} value={s.id} checked={s.id === sizeId} onChange={() => setSizeId(s.id)} />
              <span className="size__label">{s.label}</span>
              <span className="size__dims">{s.dimensions}</span>
            </label>
          ))}
        </fieldset>

        <button className="button button--clay print__add" onClick={() => add(print.id, sizeId)}>
          Add to bag
        </button>
      </div>
    </article>
  );
}

export function Shop() {
  return (
    <section className="shop" id="prints" aria-label="Print shop">
      <header className="section-head section-head--light">
        <p className="eyebrow"><span className="eyebrow__num">02</span> Print shop</p>
        <SplitText as="h2" by="words" className="section-title" interval={60}>
          Hang them where they nap.
        </SplitText>
        <p className="section-lede">
          Archival giclée prints on cotton rag, made to order and signed by Jason. Shipped flat in
          rigid packaging, unframed.
        </p>
      </header>

      <ScrollReveal className="prints" stagger={120} distance={56} duration={950}>
        {prints.map((print, i) => (
          <PrintCard key={print.id} print={print} index={i} />
        ))}
      </ScrollReveal>

      <ul className="promises">
        <li><span>Archival inks</span> rated for a lifetime indoors</li>
        <li><span>Made to order</span> and dispatched within 7 working days</li>
        <li><span>Secure checkout</span> by Stripe, cards, Apple Pay and Google Pay</li>
      </ul>
    </section>
  );
}

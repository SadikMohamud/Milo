import Image from 'next/image';
import type { CSSProperties } from 'react';
import type { Work } from '@/lib/catalogue';
import { Paw } from './Paw';

interface PlateProps {
  work: Work;
  sizes: string;
  priority?: boolean;
  /** Small renders (bag thumbnails) drop the caption. */
  compact?: boolean;
}

// A portrait in the collection. Shows the photograph when one is set, otherwise a toned card in the work's colours.
export function Plate({ work, sizes, priority, compact }: PlateProps) {
  if (work.image) {
    return (
      <div className="plate">
        <Image src={work.image} alt={`${work.name}, ${work.breed}`} fill sizes={sizes} priority={priority} className="plate__img" />
      </div>
    );
  }
  const [ground, mark] = work.tones;
  return (
    <div className="plate plate--toned" style={{ '--ground': ground, '--mark': mark } as CSSProperties} role="img" aria-label={`${work.name}, ${work.breed}`}>
      <Paw className="plate__paw" />
      {!compact && (
        <span className="plate__caption" aria-hidden="true">
          <span className="plate__name">{work.name}</span>
          <span className="plate__breed">{work.breed}</span>
        </span>
      )}
    </div>
  );
}

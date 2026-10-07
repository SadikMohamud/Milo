// Single source of truth for the portfolio and the print shop.
// Prices live here and are read on the server at checkout, so the browser can never set its own price.
//
// Photos: drop files into /public/work and set `image` (for example '/work/biscuit.jpg').
// Until a photo is set, the plate renders as an art-directed colour card in its tones.

export type Category = 'Studio' | 'Outdoor' | 'Puppies';

export interface Work {
  id: string;
  name: string;
  breed: string;
  category: Category;
  image?: string;
  /** Two colours for the plate when no photo is set: ground and paw. */
  tones: [string, string];
  /** Portrait or landscape crop in the grid. */
  shape: 'tall' | 'wide' | 'square';
}

export interface PrintSize {
  id: string;
  label: string;
  dimensions: string;
  /** Price in pence. */
  price: number;
}

export interface Print {
  id: string;
  workId: string;
  title: string;
  edition: string;
  paper: string;
}

export const currency = 'gbp';

export const works: Work[] = [
  { id: 'biscuit', name: 'Biscuit', breed: 'Cocker Spaniel', category: 'Studio', tones: ['#D9B48F', '#3B2416'], shape: 'tall' },
  { id: 'otis', name: 'Otis', breed: 'French Bulldog', category: 'Studio', tones: ['#2E3B36', '#E8DCC8'], shape: 'square' },
  { id: 'luna', name: 'Luna', breed: 'Whippet', category: 'Outdoor', tones: ['#B9C2B0', '#2A2C24'], shape: 'wide' },
  { id: 'pip', name: 'Pip', breed: 'Dachshund pup', category: 'Puppies', tones: ['#E7C9B5', '#7A3322'], shape: 'square' },
  { id: 'murphy', name: 'Murphy', breed: 'Labrador', category: 'Outdoor', tones: ['#C58A4E', '#1E1712'], shape: 'tall' },
  { id: 'nell', name: 'Nell', breed: 'Border Collie', category: 'Outdoor', tones: ['#1F2226', '#EDE6DA'], shape: 'tall' },
  { id: 'bramble', name: 'Bramble', breed: 'Cockapoo pup', category: 'Puppies', tones: ['#D6C1A3', '#4A3526'], shape: 'wide' },
  { id: 'hugo', name: 'Hugo', breed: 'Great Dane', category: 'Studio', tones: ['#6E6A63', '#F1EBE1'], shape: 'square' },
  { id: 'mabel', name: 'Mabel', breed: 'Staffordshire Bull Terrier', category: 'Studio', tones: ['#B8461F', '#F1EBE1'], shape: 'tall' },
  { id: 'scout', name: 'Scout', breed: 'Golden Retriever pup', category: 'Puppies', tones: ['#E3B66E', '#3A2A12'], shape: 'square' },
];

export const sizes: PrintSize[] = [
  { id: 'a4', label: 'A4', dimensions: '21 × 29.7 cm', price: 4500 },
  { id: 'a3', label: 'A3', dimensions: '29.7 × 42 cm', price: 7500 },
  { id: 'a2', label: 'A2', dimensions: '42 × 59.4 cm', price: 12000 },
];

export const prints: Print[] = [
  { id: 'biscuit-print', workId: 'biscuit', title: 'Biscuit, Sitting Pretty', edition: 'Open edition', paper: 'Hahnemühle Photo Rag 308gsm' },
  { id: 'luna-print', workId: 'luna', title: 'Luna at First Light', edition: 'Limited to 50', paper: 'Hahnemühle Photo Rag 308gsm' },
  { id: 'otis-print', workId: 'otis', title: 'Otis, Unimpressed', edition: 'Open edition', paper: 'Hahnemühle Photo Rag 308gsm' },
  { id: 'nell-print', workId: 'nell', title: 'Nell in the Long Grass', edition: 'Limited to 50', paper: 'Hahnemühle Photo Rag 308gsm' },
  { id: 'mabel-print', workId: 'mabel', title: 'Mabel, Red Collar', edition: 'Open edition', paper: 'Hahnemühle Photo Rag 308gsm' },
  { id: 'scout-print', workId: 'scout', title: 'Scout, Eight Weeks', edition: 'Open edition', paper: 'Hahnemühle Photo Rag 308gsm' },
];

/** Flat UK shipping in pence, offered at Stripe Checkout. */
export const shipping = { standard: 595, tracked: 995 };

export const findWork = (id: string) => works.find((w) => w.id === id);
export const findPrint = (id: string) => prints.find((p) => p.id === id);
export const findSize = (id: string) => sizes.find((s) => s.id === id);

export function formatPrice(pence: number): string {
  return new Intl.NumberFormat('en-GB', { style: 'currency', currency: currency.toUpperCase(), minimumFractionDigits: 0 }).format(pence / 100);
}

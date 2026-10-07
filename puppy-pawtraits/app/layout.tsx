import type { Metadata, Viewport } from 'next';
import { Familjen_Grotesk, Gloock, JetBrains_Mono } from 'next/font/google';
import type { ReactNode } from 'react';
import { CartProvider } from '@/components/Cart';
import { CursorFollower } from '@/components/mechanics/CursorFollower';
import { SmoothScroll } from '@/components/mechanics/SmoothScroll';
import { site } from '@/lib/site';
import './globals.css';

const display = Gloock({ subsets: ['latin'], weight: '400', variable: '--font-display' });
const body = Familjen_Grotesk({ subsets: ['latin'], variable: '--font-body' });
const mono = JetBrains_Mono({ subsets: ['latin'], weight: ['400', '500'], variable: '--font-mono' });

export const metadata: Metadata = {
  title: `${site.name} | Dog portraits by ${site.photographer}`,
  description: site.description,
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? 'http://localhost:3000'),
  openGraph: { title: site.name, description: site.description, images: ['/brand/logo-ink.png'] },
};

export const viewport: Viewport = { themeColor: '#F1EBE1' };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en-GB" className={`${display.variable} ${body.variable} ${mono.variable}`}>
      <body>
        <a href="#work" className="skip">Skip to the work</a>
        <SmoothScroll lerp={0.09}>
          <CartProvider>{children}</CartProvider>
        </SmoothScroll>
        <CursorFollower size={12} hoverScale={3.2} />
      </body>
    </html>
  );
}

import type { Metadata } from 'next';
import Image from 'next/image';
import Stripe from 'stripe';
import { site } from '@/lib/site';
import { ClearCart } from './ClearCart';

export const metadata: Metadata = { title: `Thank you | ${site.name}`, robots: { index: false } };

async function customerName(sessionId: string | undefined): Promise<string | null> {
  const key = process.env.STRIPE_SECRET_KEY;
  if (!key || !sessionId?.startsWith('cs_')) return null;
  try {
    const session = await new Stripe(key).checkout.sessions.retrieve(sessionId);
    if (session.payment_status !== 'paid') return null;
    return session.customer_details?.name?.split(' ')[0] ?? null;
  } catch {
    return null;
  }
}

export default async function Success({ searchParams }: { searchParams: Promise<{ session_id?: string }> }) {
  const { session_id } = await searchParams;
  const name = await customerName(session_id);

  return (
    <main className="success">
      <ClearCart />
      <Image src="/brand/logo-ink.png" alt={site.name} width={1502} height={951} className="success__logo" priority sizes="280px" />
      <p className="eyebrow">Order received</p>
      <h1 className="success__title">Thank you{name ? `, ${name}` : ''}.</h1>
      <p className="success__body">
        Your print is now in the queue. A receipt is on its way to your inbox, and we will email again
        when it ships. Questions? Write to <a href={`mailto:${site.email}`}>{site.email}</a>.
      </p>
      <a href="/" className="button button--ink">Back to the gallery</a>
    </main>
  );
}

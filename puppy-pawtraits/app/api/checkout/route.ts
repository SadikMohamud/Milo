import Stripe from 'stripe';
import { currency, findPrint, findSize, shipping } from '@/lib/catalogue';

export const runtime = 'nodejs';

interface RequestItem {
  printId: unknown;
  sizeId: unknown;
  quantity: unknown;
}

const MAX_LINES = 20;
const MAX_QUANTITY = 10;

function fail(error: string, status: number) {
  return Response.json({ error }, { status });
}

// Builds a Stripe Checkout session from the bag. Every price comes from the catalogue on the server;
// the request only names which prints, which sizes and how many.
export async function POST(request: Request) {
  const key = process.env.STRIPE_SECRET_KEY;
  if (!key) return fail('Checkout is not configured yet. Add STRIPE_SECRET_KEY to the environment.', 503);

  let items: RequestItem[];
  try {
    const body = (await request.json()) as { items?: unknown };
    if (!Array.isArray(body.items)) throw new Error();
    items = body.items as RequestItem[];
  } catch {
    return fail('The bag could not be read.', 400);
  }
  if (items.length === 0) return fail('Your bag is empty.', 400);
  if (items.length > MAX_LINES) return fail('Too many different prints in one order.', 400);

  const lineItems: Stripe.Checkout.SessionCreateParams.LineItem[] = [];
  for (const item of items) {
    const print = typeof item.printId === 'string' ? findPrint(item.printId) : undefined;
    const size = typeof item.sizeId === 'string' ? findSize(item.sizeId) : undefined;
    const quantity = Number(item.quantity);
    if (!print || !size || !Number.isInteger(quantity) || quantity < 1 || quantity > MAX_QUANTITY) {
      return fail('Something in your bag is no longer available. Please refresh and try again.', 400);
    }
    lineItems.push({
      quantity,
      price_data: {
        currency,
        unit_amount: size.price,
        product_data: {
          name: `${print.title} (${size.label})`,
          description: `${size.dimensions}, ${print.paper}. ${print.edition}.`,
          metadata: { printId: print.id, sizeId: size.id },
        },
      },
    });
  }

  const origin = process.env.NEXT_PUBLIC_SITE_URL ?? new URL(request.url).origin;
  const stripe = new Stripe(key);

  try {
    const session = await stripe.checkout.sessions.create({
      mode: 'payment',
      line_items: lineItems,
      shipping_address_collection: { allowed_countries: ['GB'] },
      shipping_options: [
        { shipping_rate_data: { display_name: 'Royal Mail, 2 to 3 working days', type: 'fixed_amount', fixed_amount: { amount: shipping.standard, currency } } },
        { shipping_rate_data: { display_name: 'Tracked, next working day', type: 'fixed_amount', fixed_amount: { amount: shipping.tracked, currency } } },
      ],
      phone_number_collection: { enabled: true },
      success_url: `${origin}/success?session_id={CHECKOUT_SESSION_ID}`,
      cancel_url: `${origin}/#prints`,
    });
    if (!session.url) return fail('Stripe did not return a checkout page.', 502);
    return Response.json({ url: session.url });
  } catch (error) {
    console.error('Stripe checkout failed', error);
    return fail('Checkout is unavailable right now. Please try again in a moment.', 502);
  }
}

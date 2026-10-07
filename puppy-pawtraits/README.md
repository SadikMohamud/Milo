# Puppy Pawtraits

Portfolio and print shop for Jason Robinson's dog portrait photography.

- **Hero**: brush logo reveal, word-by-word headline, a parallax stack of portraits and a running services band.
- **Work**: filterable gallery (Studio, Outdoor, Puppies) with scroll reveals and a keyboard-friendly lightbox.
- **Prints**: size picker, a bag that remembers its contents, and Stripe Checkout with UK shipping options.
- **Commission**: how a session works, contact and footer.

Built with Next.js 15 (App Router) and TypeScript. Motion comes from the MiMic mechanics in `components/mechanics`
(SmoothScroll, SplitText, ScrollReveal, Parallax, Magnetic, Marquee, CursorFollower), all of which settle to their
end state for visitors who prefer reduced motion.

## Run it

```sh
npm install
cp .env.example .env.local   # add your Stripe secret key
npm run dev
```

## Before launch

1. **Photos.** Put images in `public/work/` and set `image` on each entry in `lib/catalogue.ts`
   (for example `image: '/work/biscuit.jpg'`). Until then each portrait shows as a toned card in its colours.
2. **Prints and prices.** Edit `prints`, `sizes` and `shipping` in `lib/catalogue.ts`. Prices are in pence and are
   read on the server at checkout, so the browser cannot change them.
3. **Studio details.** Email and Instagram live in `lib/site.ts`.
4. **Stripe.** Set `STRIPE_SECRET_KEY` and `NEXT_PUBLIC_SITE_URL` in the hosting environment. Test with
   `sk_test_...` keys and card `4242 4242 4242 4242` first. Paid orders appear in the Stripe Dashboard with the
   customer's shipping address, ready to fulfil.

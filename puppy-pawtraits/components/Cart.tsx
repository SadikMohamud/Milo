'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { findPrint, findSize, findWork, formatPrice } from '@/lib/catalogue';
import { Plate } from './Plate';

export interface CartItem {
  printId: string;
  sizeId: string;
  quantity: number;
}

interface CartState {
  items: CartItem[];
  count: number;
  open: boolean;
  setOpen: (open: boolean) => void;
  add: (printId: string, sizeId: string) => void;
  setQuantity: (printId: string, sizeId: string, quantity: number) => void;
  clear: () => void;
}

const CartContext = createContext<CartState | null>(null);
export const STORAGE_KEY = 'pp-cart-v1';
const MAX_QUANTITY = 10;

export function useCart(): CartState {
  const cart = useContext(CartContext);
  if (!cart) throw new Error('useCart must be used inside CartProvider');
  return cart;
}

export function CartProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<CartItem[]>([]);
  const [open, setOpen] = useState(false);
  const loaded = useRef(false);

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '[]') as CartItem[];
      setItems(saved.filter((i) => findPrint(i.printId) && findSize(i.sizeId)));
    } catch {
      // storage unavailable or corrupt: start with an empty bag
    }
    loaded.current = true;
  }, []);

  useEffect(() => {
    if (!loaded.current) return;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    } catch {
      // private mode: the bag still works for this visit
    }
  }, [items]);

  const add = useCallback((printId: string, sizeId: string) => {
    setItems((current) => {
      const existing = current.find((i) => i.printId === printId && i.sizeId === sizeId);
      if (existing) {
        return current.map((i) => (i === existing ? { ...i, quantity: Math.min(MAX_QUANTITY, i.quantity + 1) } : i));
      }
      return [...current, { printId, sizeId, quantity: 1 }];
    });
    setOpen(true);
  }, []);

  const setQuantity = useCallback((printId: string, sizeId: string, quantity: number) => {
    setItems((current) =>
      quantity <= 0
        ? current.filter((i) => !(i.printId === printId && i.sizeId === sizeId))
        : current.map((i) => (i.printId === printId && i.sizeId === sizeId ? { ...i, quantity: Math.min(MAX_QUANTITY, quantity) } : i)),
    );
  }, []);

  const clear = useCallback(() => setItems([]), []);

  const value = useMemo(
    () => ({ items, count: items.reduce((n, i) => n + i.quantity, 0), open, setOpen, add, setQuantity, clear }),
    [items, open, add, setQuantity, clear],
  );

  return (
    <CartContext.Provider value={value}>
      {children}
      <CartDrawer />
    </CartContext.Provider>
  );
}

function CartDrawer() {
  const { items, open, setOpen, setQuantity } = useCart();
  const [status, setStatus] = useState<'idle' | 'loading' | 'error'>('idle');
  const [message, setMessage] = useState('');
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && setOpen(false);
    document.addEventListener('keydown', onKey);
    document.documentElement.classList.add('is-locked');
    return () => {
      document.removeEventListener('keydown', onKey);
      document.documentElement.classList.remove('is-locked');
    };
  }, [open, setOpen]);

  const subtotal = items.reduce((sum, i) => sum + (findSize(i.sizeId)?.price ?? 0) * i.quantity, 0);

  async function checkout() {
    setStatus('loading');
    setMessage('');
    try {
      const response = await fetch('/api/checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items }),
      });
      const data = (await response.json()) as { url?: string; error?: string };
      if (!response.ok || !data.url) throw new Error(data.error ?? 'Checkout is unavailable right now.');
      window.location.assign(data.url);
    } catch (error) {
      setStatus('error');
      setMessage(error instanceof Error ? error.message : 'Checkout is unavailable right now.');
    }
  }

  return (
    <div className="cart" data-open={open} aria-hidden={!open}>
      <button className="cart__scrim" tabIndex={-1} aria-label="Close bag" onClick={() => setOpen(false)} />
      <aside className="cart__panel" role="dialog" aria-modal="true" aria-label="Your bag" inert={!open}>
        <header className="cart__head">
          <p className="eyebrow">Your bag</p>
          <button ref={closeRef} className="cart__close" onClick={() => setOpen(false)}>Close</button>
        </header>

        {items.length === 0 ? (
          <div className="cart__empty">
            <p className="cart__empty-title">Nothing here yet.</p>
            <p>Choose a print and a size, and it will wait for you here.</p>
          </div>
        ) : (
          <ul className="cart__list">
            {items.map((item) => {
              const print = findPrint(item.printId)!;
              const size = findSize(item.sizeId)!;
              const work = findWork(print.workId)!;
              return (
                <li key={`${item.printId}-${item.sizeId}`} className="cart__item">
                  <div className="cart__thumb"><Plate work={work} sizes="80px" compact /></div>
                  <div className="cart__meta">
                    <p className="cart__title">{print.title}</p>
                    <p className="cart__detail">{size.label}, {size.dimensions}</p>
                    <div className="qty" role="group" aria-label={`Quantity of ${print.title}`}>
                      <button onClick={() => setQuantity(item.printId, item.sizeId, item.quantity - 1)} aria-label="One fewer">−</button>
                      <span aria-live="polite">{item.quantity}</span>
                      <button onClick={() => setQuantity(item.printId, item.sizeId, item.quantity + 1)} aria-label="One more" disabled={item.quantity >= MAX_QUANTITY}>+</button>
                    </div>
                  </div>
                  <p className="cart__price">{formatPrice(size.price * item.quantity)}</p>
                </li>
              );
            })}
          </ul>
        )}

        <footer className="cart__foot">
          <div className="cart__total">
            <span>Subtotal</span>
            <span>{formatPrice(subtotal)}</span>
          </div>
          <p className="cart__note">Shipping is chosen at checkout. Payments are handled securely by Stripe.</p>
          <button className="button button--clay cart__checkout" onClick={checkout} disabled={items.length === 0 || status === 'loading'}>
            {status === 'loading' ? 'Opening checkout…' : 'Checkout'}
          </button>
          {status === 'error' && <p className="cart__error" role="alert">{message}</p>}
        </footer>
      </aside>
    </div>
  );
}

'use client';

import { useEffect } from 'react';
import { STORAGE_KEY, useCart } from '@/components/Cart';

// Empties the bag once the visitor lands back from a completed checkout. Storage is cleared directly as well,
// because this effect runs before the provider restores the saved bag.
export function ClearCart() {
  const { clear } = useCart();
  useEffect(() => {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      // storage unavailable: clearing state is enough
    }
    clear();
  }, [clear]);
  return null;
}

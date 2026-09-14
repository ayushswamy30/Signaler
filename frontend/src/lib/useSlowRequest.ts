"use client";

import { useEffect, useState } from "react";

/** True once a pending request has been running long enough to look stuck.
 *
 *  A spinner says "working"; it does not say "this may take a minute", and on
 *  a backend that sleeps after 15 minutes without traffic the difference
 *  matters -- the first sign-in after an idle spell really does take that
 *  long, and a button that has spun silently for 40 seconds reads as a broken
 *  form rather than a slow one. */
export function useSlowRequest(pending: boolean, afterMs = 4000): boolean {
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    if (!pending) {
      setSlow(false);
      return;
    }
    const timer = setTimeout(() => setSlow(true), afterMs);
    return () => clearTimeout(timer);
  }, [pending, afterMs]);

  return slow;
}

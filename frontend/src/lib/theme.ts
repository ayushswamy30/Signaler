"use client";

/** Tracks the `data-theme` attribute layout.tsx's pre-paint script sets on
 *  <html> (see ThemeToggle's useTheme, which flips it later). Kept separate
 *  from that hook because callers here -- the loading screen, the auth
 *  card's background -- only need to *read* the current theme, not manage a
 *  toggle button, and every page already has the attribute set before this
 *  ever mounts. */

import { useEffect, useState } from "react";

export function useIsDarkTheme(): boolean {
  const [isDark, setIsDark] = useState(false);

  useEffect(() => {
    const read = () => setIsDark(document.documentElement.getAttribute("data-theme") === "dark");
    read();
    const observer = new MutationObserver(read);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => observer.disconnect();
  }, []);

  return isDark;
}

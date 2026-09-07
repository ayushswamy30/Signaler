"use client";
import { useEffect, useState } from "react";
import { Icon } from "./Icon";

type Theme = "light" | "dark";

export function useTheme() {
  const [theme, setTheme] = useState<Theme>("light");
  useEffect(() => {
    const stored = (localStorage.getItem("signaler-theme") as Theme | null);
    const initial = stored ?? (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    setTheme(initial);
    document.documentElement.setAttribute("data-theme", initial);
  }, []);
  function toggle(next?: Theme) {
    const value = next ?? (theme === "light" ? "dark" : "light");
    setTheme(value);
    document.documentElement.setAttribute("data-theme", value);
    try { localStorage.setItem("signaler-theme", value); } catch {}
  }
  return { theme, toggle };
}

export function ThemeToggle() {
  const { theme, toggle } = useTheme();
  return (
    <button onClick={() => toggle()} aria-label={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
      className="inline-flex h-11 w-11 items-center justify-center rounded-md text-ink-muted
        hover:bg-hover hover:text-ink md:h-9 md:w-9">
      <Icon name={theme === "light" ? "moon" : "sun"} size={19} />
    </button>
  );
}

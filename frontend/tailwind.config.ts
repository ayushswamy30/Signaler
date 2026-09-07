import type { Config } from "tailwindcss";

/** Every colour maps to a CSS variable from globals.css — see design/design-tokens.md. */
const token = (name: string) => `var(--color-${name})`;

export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: token("bg-canvas"),
        surface: token("bg-surface"),
        raised: token("bg-surface-raised"),
        sidebar: token("bg-sidebar"),
        hover: token("bg-hover"),
        active: token("bg-active"),
        ink: { DEFAULT: token("text-primary"), muted: token("text-secondary"), faint: token("text-tertiary"), inverse: token("text-inverse"), link: token("text-link"), danger: token("text-danger"), onAccent: token("text-on-accent") },
        line: { subtle: token("border-subtle"), DEFAULT: token("border-default"), strong: token("border-strong"), focus: token("border-focus") },
        accent: { DEFAULT: token("accent-default"), hover: token("accent-hover"), pressed: token("accent-pressed"), subtle: token("accent-subtle") },
        bubble: { out: token("bubble-outgoing-bg"), outText: token("bubble-outgoing-text"), in: token("bubble-incoming-bg"), inText: token("bubble-incoming-text"), quote: token("bubble-quote-bg"), quoteBorder: token("bubble-quote-border") },
        status: { online: token("status-online"), success: token("status-success"), danger: token("status-danger"), warning: token("status-warning"), unread: token("status-unread-bg"), unreadText: token("status-unread-text") },
      },
      spacing: { "2xs": "2px", xs: "4px", sm: "8px", md: "12px", lg: "16px", xl: "24px", "2xl": "32px", "3xl": "48px", "4xl": "64px" },
      borderRadius: { sm: "4px", md: "8px", lg: "12px", xl: "16px", "2xl": "20px" },
      fontSize: {
        xs: ["11px", "16px"], sm: ["12px", "16px"], md: ["13px", "18px"],
        base: ["14px", "20px"], lg: ["16px", "24px"], xl: ["20px", "28px"],
        "2xl": ["24px", "32px"], "3xl": ["32px", "40px"],
      },
      fontFamily: { sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "sans-serif"] },
      boxShadow: {
        xs: "0 1px 2px rgba(0,0,0,.06)", sm: "0 2px 6px rgba(0,0,0,.08)",
        md: "0 4px 12px rgba(0,0,0,.10)", lg: "0 8px 24px rgba(0,0,0,.14)",
      },
    },
  },
  plugins: [],
} satisfies Config;

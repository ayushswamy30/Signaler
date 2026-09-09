import type { LightTunnelProps } from "@/components/LightTunnel";

/** LightTunnel color presets tied to the app's accent tokens (globals.css),
 *  so the background reads as "Signaler blue" rather than the component's
 *  default purple, and stays in sync with the light/dark toggle. Kept out
 *  of the two call sites (AuthShell, the boot screen) so both stay in sync
 *  if the palette ever moves. */
export const TUNNEL_COLORS: Record<"light" | "dark", Pick<LightTunnelProps, "cableColor" | "pulseColor" | "tunnelColor">> = {
  light: {
    cableColor: "#2C6BED", // --color-accent-default
    pulseColor: "#1E55C9", // --color-accent-hover
    tunnelColor: "#17429C", // --color-accent-pressed
  },
  dark: {
    cableColor: "#4B8BFF", // --color-accent-default
    pulseColor: "#7BAAFF", // --color-accent-hover
    tunnelColor: "#2C6BED", // --color-accent-pressed
  },
};

import type { SVGProps } from "react";

const paths: Record<string, string> = {
  search: "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14M20 20l-3.2-3.2",
  edit: "M4 20h4L19 9a2.1 2.1 0 0 0-3-3L5 17v3z",
  settings: "M4 7h10M18 7h2M4 12h2M10 12h10M4 17h8M16 17h4M16 7a2 2 0 1 0 0-.1M8 12a2 2 0 1 0 0-.1M14 17a2 2 0 1 0 0-.1",
  more: "M12 4.6a1.4 1.4 0 1 0 0 2.8 1.4 1.4 0 0 0 0-2.8M12 10.6a1.4 1.4 0 1 0 0 2.8 1.4 1.4 0 0 0 0-2.8M12 17.6a1.4 1.4 0 1 0 0 2.8 1.4 1.4 0 0 0 0-2.8",
  phone: "M6 3h4l2 5-2.5 1.5a11 11 0 0 0 5 5L16 12l5 2v4a2 2 0 0 1-2.2 2A16 16 0 0 1 4 5.2 2 2 0 0 1 6 3z",
  video: "M5.5 6h7A2.5 2.5 0 0 1 15 8.5v7a2.5 2.5 0 0 1-2.5 2.5h-7A2.5 2.5 0 0 1 3 15.5v-7A2.5 2.5 0 0 1 5.5 6M15 10.5l6-3.5v10l-6-3.5z",
  info: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18M12 11v5M12 7.6v.1",
  send: "M4 12l16-8-6 8 6 8-16-8z",
  smile: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18M8.5 14.5a4.5 4.5 0 0 0 7 0M9 9.5v.1M15 9.5v.1",
  clip: "M17 8l-7.6 7.6a2.5 2.5 0 0 0 3.5 3.5L21 11a4.5 4.5 0 0 0-6.4-6.4L6 13.2",
  back: "M15 5l-7 7 7 7",
  check: "M5 12.5l4.5 4.5L19 7",
  checks: "M2 12.5l4 4L14 8M10 15.5l1.5 1.5L21 7",
  close: "M6 6l12 12M18 6L6 18",
  plus: "M12 5v14M5 12h14",
  users: "M9 5.8a3.2 3.2 0 1 0 0 6.4 3.2 3.2 0 0 0 0-6.4M3 19a6 6 0 0 1 12 0M16.5 7.2a3 3 0 0 1 0 5.6M17 19a6 6 0 0 0-2-4.3",
  bell: "M18 9a6 6 0 0 0-12 0c0 5-2 6-2 6h16s-2-1-2-6M13.7 20a2 2 0 0 1-3.4 0",
  lock: "M6.7 10.5h10.6A2.2 2.2 0 0 1 19.5 12.7v5.6a2.2 2.2 0 0 1-2.2 2.2H6.7a2.2 2.2 0 0 1-2.2-2.2v-5.6a2.2 2.2 0 0 1 2.2-2.2M8 10.5V7.8a4 4 0 0 1 8 0v2.7",
  palette: "M12 3a9 9 0 1 0 0 18c1.4 0 1.8-1 1.2-1.8-.7-1 .1-2.2 1.4-2.2H17a4 4 0 0 0 4-4c0-5-4-10-9-10M8 10a1 1 0 1 0 0 2 1 1 0 0 0 0-2M12 7a1 1 0 1 0 0 2 1 1 0 0 0 0-2M16 10a1 1 0 1 0 0 2 1 1 0 0 0 0-2",
  devices: "M4.8 5h8.4A1.8 1.8 0 0 1 15 6.8v5.4A1.8 1.8 0 0 1 13.2 14H4.8A1.8 1.8 0 0 1 3 12.2V6.8A1.8 1.8 0 0 1 4.8 5M6 18h6M17.5 9h2A1.5 1.5 0 0 1 21 10.5v7A1.5 1.5 0 0 1 19.5 19h-2A1.5 1.5 0 0 1 16 17.5v-7A1.5 1.5 0 0 1 17.5 9",
  chevron: "M9 5l7 7-7 7",
  camera: "M4 8h3l1.5-2h7L17 8h3a1.6 1.6 0 0 1 1.6 1.6v8A1.6 1.6 0 0 1 20 19H4a1.6 1.6 0 0 1-1.6-1.6v-8A1.6 1.6 0 0 1 4 8M12 9.6a3.4 3.4 0 1 0 0 6.8 3.4 3.4 0 0 0 0-6.8",
  reply: "M9 7L4 12l5 5M4 12h9a6 6 0 0 1 6 6v1",
  warn: "M12 4.5L21 19H3zM12 10v4M12 16.6v.1",
  wifi: "M2.5 9.5a15 15 0 0 1 19 0M6 13a10 10 0 0 1 12 0M9.5 16.5a5 5 0 0 1 5 0M12 20v.1",
  mute: "M18 9a6 6 0 0 0-9.3-5M6 9c0 5-2 6-2 6h11M13.7 20a2 2 0 0 1-3.4 0M3.5 3.5l17 17",
  arrowDown: "M12 5v14M6 13l6 6 6-6",
  moon: "M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5",
  sun: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8M12 2v2M12 20v2M22 12h-2M4 12H2M18.4 5.6l-1.4 1.4M7 17l-1.4 1.4M18.4 18.4L17 17M7 7L5.6 5.6",
};

export type IconName = keyof typeof paths;

interface Props extends SVGProps<SVGSVGElement> {
  name: IconName; size?: number; strokeWidth?: number;
}

export function Icon({ name, size = 20, strokeWidth = 1.6, ...rest }: Props) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round"
      aria-hidden="true" {...rest}>
      <path d={paths[name]} />
    </svg>
  );
}

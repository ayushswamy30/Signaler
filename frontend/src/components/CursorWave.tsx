"use client";

/** A grid of small shapes that swells near the pointer and rings outward from
 *  a click -- a background effect, not a foreground one: it sits behind the
 *  content, and `avoidRef` keeps it from drawing under a specific element at
 *  all (the logo, the card holding the login/signup form), so it never
 *  visually competes with what someone is actually looking at or typing into.
 *
 *  Hand-rolled rather than a packaged "cursor effect" component -- nothing
 *  else in this UI depends on an external component registry (see Icon.tsx),
 *  and a paid one needs a license key this environment does not have. Same
 *  gating as the effect it replaces: no motion for anyone who asked for less,
 *  and desktop only, since a hover grid means nothing on a touchscreen. */

import { useEffect, useRef, type RefObject } from "react";

const SPACING = 40; // px between grid points
const BASE_SIZE = 2.5; // resting shape radius
const MAX_SIZE = 8; // shape radius at full influence
const BASE_ALPHA = 0.18;
const MAX_ALPHA = 0.9;
const POINTER_RADIUS = 160; // px of influence around the cursor
const DISPLACE = 6; // px a shape is pushed away from the cursor at full influence
const RIPPLE_LIFE = 900; // ms a click ripple lasts
const RIPPLE_MAX_RADIUS = 260; // px the ripple ring expands to
const RIPPLE_BAND = 34; // px width of the ring
const MAX_RIPPLES = 6;
const AVOID_PADDING = 20; // px clearance kept around avoidRef's box

interface Ripple { x: number; y: number; start: number }

export function CursorWave({ avoidRef }: { avoidRef?: RefObject<HTMLElement | null> }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;

    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    if (!window.matchMedia("(pointer: fine)").matches) return;

    let width = 0, height = 0;
    let color = "#2C6BED";
    let avoid: { left: number; right: number; top: number; bottom: number } | null = null;

    function readColor() {
      const value = getComputedStyle(document.documentElement)
        .getPropertyValue("--color-accent-default").trim();
      if (value) color = value;
    }

    function measureAvoid() {
      const box = avoidRef?.current?.getBoundingClientRect();
      avoid = box
        ? {
            left: box.left - AVOID_PADDING, right: box.right + AVOID_PADDING,
            top: box.top - AVOID_PADDING, bottom: box.bottom + AVOID_PADDING,
          }
        : null;
    }

    function resize() {
      const dpr = window.devicePixelRatio || 1;
      width = window.innerWidth;
      height = window.innerHeight;
      canvas!.width = width * dpr;
      canvas!.height = height * dpr;
      canvas!.style.width = `${width}px`;
      canvas!.style.height = `${height}px`;
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
      measureAvoid();
    }

    let pointerX = -9999, pointerY = -9999;
    function onPointerMove(e: PointerEvent) {
      pointerX = e.clientX;
      pointerY = e.clientY;
    }
    function onPointerLeave() {
      pointerX = -9999;
      pointerY = -9999;
    }

    const ripples: Ripple[] = [];
    function onPointerDown(e: PointerEvent) {
      ripples.push({ x: e.clientX, y: e.clientY, start: performance.now() });
      if (ripples.length > MAX_RIPPLES) ripples.shift();
    }

    resize();
    readColor();
    window.addEventListener("resize", resize);
    window.addEventListener("pointermove", onPointerMove, { passive: true });
    window.addEventListener("pointerleave", onPointerLeave);
    window.addEventListener("pointerdown", onPointerDown, { passive: true });
    // The layout the avoid box sits in can shift after fonts/images settle;
    // a periodic remeasure is simpler than wiring a ResizeObserver for a
    // purely decorative effect.
    const remeasure = window.setInterval(measureAvoid, 1000);
    const themeObserver = new MutationObserver(readColor);
    themeObserver.observe(document.documentElement, {
      attributes: true, attributeFilter: ["data-theme"],
    });

    let frame = requestAnimationFrame(tick);
    function tick() {
      frame = requestAnimationFrame(tick);
      const now = performance.now();

      // Oldest first, so a full ring array still empties in order.
      while (ripples.length && now - ripples[0].start > RIPPLE_LIFE) ripples.shift();

      ctx!.clearRect(0, 0, width, height);
      ctx!.fillStyle = color;

      const cols = Math.ceil(width / SPACING) + 1;
      const rows = Math.ceil(height / SPACING) + 1;

      for (let row = 0; row < rows; row++) {
        for (let col = 0; col < cols; col++) {
          const gx = col * SPACING;
          const gy = row * SPACING;

          if (avoid && gx >= avoid.left && gx <= avoid.right && gy >= avoid.top && gy <= avoid.bottom) {
            continue;
          }

          const dx = gx - pointerX, dy = gy - pointerY;
          const dist = Math.hypot(dx, dy);
          const pointerInfluence = dist < POINTER_RADIUS ? 1 - dist / POINTER_RADIUS : 0;

          let rippleInfluence = 0;
          for (const ripple of ripples) {
            const age = now - ripple.start;
            const progress = age / RIPPLE_LIFE;
            const radius = progress * RIPPLE_MAX_RADIUS;
            const band = Math.abs(Math.hypot(gx - ripple.x, gy - ripple.y) - radius);
            if (band < RIPPLE_BAND) {
              rippleInfluence = Math.max(rippleInfluence, (1 - band / RIPPLE_BAND) * (1 - progress));
            }
          }

          const influence = Math.min(1, pointerInfluence + rippleInfluence);
          if (influence <= 0.01) {
            // Still worth a faint resting dot so the grid reads as a grid.
            ctx!.globalAlpha = BASE_ALPHA;
            ctx!.beginPath();
            ctx!.arc(gx, gy, BASE_SIZE, 0, Math.PI * 2);
            ctx!.fill();
            continue;
          }

          const push = pointerInfluence > 0 && dist > 0.01 ? (DISPLACE * pointerInfluence) / dist : 0;
          const size = BASE_SIZE + influence * (MAX_SIZE - BASE_SIZE);
          const alpha = BASE_ALPHA + influence * (MAX_ALPHA - BASE_ALPHA);

          ctx!.globalAlpha = Math.min(1, alpha);
          ctx!.beginPath();
          ctx!.arc(gx + dx * push, gy + dy * push, size, 0, Math.PI * 2);
          ctx!.fill();
        }
      }
      ctx!.globalAlpha = 1;
    }

    return () => {
      cancelAnimationFrame(frame);
      window.clearInterval(remeasure);
      window.removeEventListener("resize", resize);
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerleave", onPointerLeave);
      window.removeEventListener("pointerdown", onPointerDown);
      themeObserver.disconnect();
    };
  }, [avoidRef]);

  return (
    <canvas ref={canvasRef} aria-hidden="true" className="pointer-events-none fixed inset-0 z-0" />
  );
}

"use client";

/** A dithered pixel trail that follows the pointer.
 *
 *  Decorative, and scoped to the boot screen and the auth pages rather than
 *  the whole app -- a message thread is for reading, not for a cursor toy.
 *
 *  Hand-rolled rather than a packaged "cursor effect" component: nothing else
 *  in this UI depends on an external component registry (see Icon.tsx), and
 *  pulling one in for a single decorative flourish would be the odd one out.
 *
 *  The pixelation is an ordered (Bayer) dither: each cell's fade is quantised
 *  against a per-position threshold instead of a smooth alpha, so the trail
 *  thins out as a spreading stipple of solid pixels rather than a blurred
 *  glow. Only recently-touched cells are tracked, so cost scales with the
 *  trail, not the screen. */

import { useEffect, useRef } from "react";

const CELL = 10; // px per dithered "pixel"
const DECAY = 0.88; // per-frame fade
const RADIUS = 2; // cells painted around the pointer each frame
const FLOOR = 0.02; // below this a cell is dropped, not just dim

// 4x4 Bayer matrix, normalised to thresholds in (0, 1).
const BAYER = [
  [0, 8, 2, 10],
  [12, 4, 14, 6],
  [3, 11, 1, 9],
  [15, 7, 13, 5],
].map((row) => row.map((v) => (v + 0.5) / 16));

export function DitherCursor() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;

    // Skip it for anyone who asked for less motion, and for touch-primary
    // devices, which have no persistent pointer to leave a trail from.
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    if (!window.matchMedia("(pointer: fine)").matches) return;

    let cols = 0;
    let rows = 0;
    let heat = new Float32Array(0);
    const active = new Set<number>();
    let color = "#2C6BED";

    function readColor() {
      const value = getComputedStyle(document.documentElement)
        .getPropertyValue("--color-accent-default").trim();
      if (value) color = value;
    }

    function resize() {
      const { innerWidth, innerHeight, devicePixelRatio } = window;
      const dpr = devicePixelRatio || 1;
      cols = Math.ceil(innerWidth / CELL);
      rows = Math.ceil(innerHeight / CELL);
      canvas!.width = cols * CELL * dpr;
      canvas!.height = rows * CELL * dpr;
      canvas!.style.width = `${innerWidth}px`;
      canvas!.style.height = `${innerHeight}px`;
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
      heat = new Float32Array(cols * rows);
      active.clear();
    }

    let pointerCol = -1;
    let pointerRow = -1;
    function onPointerMove(e: PointerEvent) {
      pointerCol = Math.floor(e.clientX / CELL);
      pointerRow = Math.floor(e.clientY / CELL);
    }
    function onPointerLeave() {
      pointerCol = -1;
      pointerRow = -1;
    }

    resize();
    readColor();
    window.addEventListener("resize", resize);
    window.addEventListener("pointermove", onPointerMove, { passive: true });
    window.addEventListener("pointerleave", onPointerLeave);
    // The boot screen and auth pages toggle light/dark via the same
    // data-theme attribute the rest of the app uses.
    const themeObserver = new MutationObserver(readColor);
    themeObserver.observe(document.documentElement, {
      attributes: true, attributeFilter: ["data-theme"],
    });

    let frame = requestAnimationFrame(tick);
    function tick() {
      frame = requestAnimationFrame(tick);

      if (pointerCol >= 0) {
        for (let dy = -RADIUS; dy <= RADIUS; dy++) {
          for (let dx = -RADIUS; dx <= RADIUS; dx++) {
            const x = pointerCol + dx, y = pointerRow + dy;
            if (x < 0 || x >= cols || y < 0 || y >= rows) continue;
            const dist = Math.hypot(dx, dy) / RADIUS;
            if (dist > 1) continue;
            const i = y * cols + x;
            heat[i] = Math.max(heat[i], 1 - dist);
            active.add(i);
          }
        }
      }

      ctx!.clearRect(0, 0, cols * CELL, rows * CELL);
      ctx!.fillStyle = color;
      for (const i of active) {
        const v = heat[i];
        const x = i % cols, y = (i / cols) | 0;
        if (v >= BAYER[y % 4][x % 4]) {
          ctx!.globalAlpha = Math.min(1, v);
          ctx!.fillRect(x * CELL, y * CELL, CELL - 1, CELL - 1);
        }
        const next = v * DECAY;
        if (next <= FLOOR) {
          heat[i] = 0;
          active.delete(i);
        } else {
          heat[i] = next;
        }
      }
      ctx!.globalAlpha = 1;
    }

    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", resize);
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerleave", onPointerLeave);
      themeObserver.disconnect();
    };
  }, []);

  return <canvas ref={canvasRef} aria-hidden="true" className="pointer-events-none fixed inset-0 z-40" />;
}

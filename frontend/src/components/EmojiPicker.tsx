"use client";

/** The emoji/sticker popover attached to the composer's smile button.
 *
 *  Emoji augment whatever is being typed, so picking one inserts it and
 *  leaves the box open for more. A sticker *is* the message -- picking one
 *  sends it immediately and closes the picker, the way a sticker tray works
 *  in every mainstream messenger.
 *
 *  Purely presentational: the caller owns open/close state and, since the
 *  toggle button lives outside this component, the outside-click handling
 *  that closes it too (see Composer). */

import { useState } from "react";
import { clsx } from "@/lib/clsx";
import { COMMON_EMOJI, STICKERS } from "@/lib/emoji";

type Tab = "emoji" | "stickers";

export function EmojiPicker({ onPickEmoji, onPickSticker }: {
  onPickEmoji: (emoji: string) => void;
  onPickSticker: (sticker: string) => void;
}) {
  const [tab, setTab] = useState<Tab>("emoji");
  const items = tab === "emoji" ? COMMON_EMOJI : STICKERS;

  return (
    <div role="dialog" aria-label="Emoji and stickers"
      className="absolute bottom-full right-0 z-20 mb-sm flex w-[276px] flex-col
        overflow-hidden rounded-lg border border-line bg-raised shadow-lg">
      <div className="flex border-b border-line-subtle">
        {(["emoji", "stickers"] as const).map((key) => (
          <button key={key} type="button" onClick={() => setTab(key)} aria-pressed={tab === key}
            className={clsx("flex-1 px-md py-sm text-sm font-medium capitalize transition-colors",
              tab === key ? "border-b-2 border-accent text-accent" : "text-ink-faint hover:text-ink")}>
            {key}
          </button>
        ))}
      </div>
      <div role="menu" className="grid max-h-[260px] grid-cols-8 gap-[2px] overflow-y-auto p-sm">
        {items.map((glyph, index) => (
          <button key={`${glyph}-${index}`} type="button" role="menuitem" aria-label={glyph}
            onClick={() => (tab === "emoji" ? onPickEmoji(glyph) : onPickSticker(glyph))}
            className="flex h-9 w-9 items-center justify-center rounded-md text-xl hover:bg-hover">
            {glyph}
          </button>
        ))}
      </div>
    </div>
  );
}

/** Emoji and stickers for the composer.
 *
 *  No picker library: the rest of the UI is hand-rolled SVG icons (see
 *  Icon.tsx), so pulling in a multi-megabyte emoji package for one button
 *  would be the odd one out. This is a curated, common subset -- not an
 *  attempt at the full Unicode emoji set. */

/** Reactions and small talk, inserted into whatever is being typed. */
export const COMMON_EMOJI: readonly string[] = [
  "😀", "😃", "😄", "😁", "😆", "😅", "🤣", "😂", "🙂", "🙃",
  "😉", "😊", "😇", "🥰", "😍", "🤩", "😘", "😋", "😛", "😜",
  "🤪", "🤗", "🤔", "🤨", "😐", "🙄", "😏", "😴", "🥱", "😮",
  "😢", "😭", "😡", "🤯", "😱", "🥳", "😎", "🤦", "🤷", "🙈",
  "👍", "👎", "👏", "🙌", "🙏", "👋", "🤝", "💪", "✌️", "🤞",
  "🤟", "🤘", "👌", "🫶", "👀", "❤️", "🧡", "💛", "💚", "💙",
  "💜", "🖤", "🤍", "💔", "💕", "💯", "🔥", "✨", "🎉", "🎊",
  "🐶", "🐱", "🍕", "🍔", "☕", "🍺", "🎂", "⭐",
];

/** Big, one-tap sends. The same pool that a message consisting only of these
 *  is enlarged to (see stickerGlyphs) -- surfaced here as one tap instead of
 *  a type-then-send. */
export const STICKERS: readonly string[] = [
  "👍", "❤️", "😂", "🎉", "🔥", "👏", "😢", "😍",
  "🙏", "💯", "😮", "🥳", "🤔", "👀", "😎", "💪",
  "🙌", "✅", "❌", "🤷", "😅", "🤯", "🥰", "😭",
];

const EMOJI_CHAR = /\p{Extended_Pictographic}/u;

/** A message that is only emoji -- one to three of them, however they got
 *  typed -- is worth the "sticker" treatment: rendered oversized and without
 *  bubble chrome, the way every mainstream messenger renders it. Returns the
 *  grapheme clusters to render, or null when the message is ordinary text.
 *
 *  `Intl.Segmenter` groups a multi-codepoint emoji (a skin tone modifier, a
 *  ZWJ family) into one cluster; every evergreen browser has it. Without it,
 *  code points are checked one at a time, which only misjudges those
 *  multi-part emoji and never the plain single-codepoint majority. */
export function stickerGlyphs(content: string): string[] | null {
  const text = content.trim();
  if (!text || text.length > 32) return null;

  const clusters = typeof Intl !== "undefined" && "Segmenter" in Intl
    ? Array.from(new Intl.Segmenter(undefined, { granularity: "grapheme" }).segment(text),
        (s) => s.segment)
    : Array.from(text);

  if (clusters.length === 0 || clusters.length > 3) return null;
  return clusters.every((glyph) => EMOJI_CHAR.test(glyph)) ? clusters : null;
}

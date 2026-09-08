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

/** Big, one-tap sends -- see markSticker/parseSticker for how a tap is told
 *  apart from someone just typing the same glyph and hitting send. */
export const STICKERS: readonly string[] = [
  "👍", "❤️", "😂", "🎉", "🔥", "👏", "😢", "😍",
  "🙏", "💯", "😮", "🥳", "🤔", "👀", "😎", "💪",
  "🙌", "✅", "❌", "🤷", "😅", "🤯", "🥰", "😭",
];

/** Marks a sticker send in the plain-text `content` a message already is --
 *  a zero-width character renders as nothing in every font, so the message
 *  looks identical to the bare glyph everywhere it is displayed as text
 *  (conversation previews, reply quotes, notifications).
 *
 *  The distinction has to live in the content itself, not be inferred from
 *  it: an emoji-only message someone *typed* stays an ordinary small bubble,
 *  and only a message actually sent from the sticker tray gets the
 *  oversized, chrome-less treatment. Guessing from shape alone (an early
 *  version of this did) made every short "👍" you typed indistinguishable
 *  from a tapped sticker. */
const STICKER_MARK = String.fromCharCode(8203); // U+200B zero-width space

export function markSticker(glyph: string): string {
  return STICKER_MARK + glyph;
}

/** The glyph to render big, or null when `content` is an ordinary message. */
export function parseSticker(content: string): string | null {
  return content.startsWith(STICKER_MARK) ? content.slice(STICKER_MARK.length) : null;
}

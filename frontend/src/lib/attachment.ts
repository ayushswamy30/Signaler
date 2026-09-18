/** File attachments, marked inside a message's plain-text `content` the same
 *  way markSticker/parseSticker mark a sticker (see lib/emoji.ts) -- a
 *  message stays "just text" everywhere else in the pipeline (replies,
 *  editing, previews, notifications), so nothing there has to know
 *  attachments exist. A different zero-width character than the sticker
 *  mark keeps the two from ever being confused. */

export interface Attachment {
  url: string;
  name: string;
  contentType: string;
  size: number;
}

const ATTACHMENT_MARK = String.fromCharCode(8204); // U+200C zero-width non-joiner

export function markAttachment(attachment: Attachment): string {
  return ATTACHMENT_MARK + JSON.stringify(attachment);
}

/** The attachment a message carries, or null when `content` is ordinary text. */
export function parseAttachment(content: string): Attachment | null {
  if (!content.startsWith(ATTACHMENT_MARK)) return null;
  try {
    const data = JSON.parse(content.slice(ATTACHMENT_MARK.length));
    if (typeof data?.url === "string" && typeof data?.name === "string") return data as Attachment;
  } catch {
    /* Malformed payload: render as an ordinary (odd-looking) text message. */
  }
  return null;
}

export function isImage(contentType: string): boolean {
  return contentType.startsWith("image/");
}

/** What to show anywhere a message is condensed to one line of text --
 *  the sidebar's last-message preview and a reply quote -- so an attachment
 *  never surfaces there as its own raw marker-and-JSON `content`. */
export function contentPreview(content: string): string {
  const attachment = parseAttachment(content);
  if (!attachment) return content;
  return isImage(attachment.contentType) ? "📷 Photo" : `📎 ${attachment.name}`;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(value < 10 ? 1 : 0)} ${units[unit]}`;
}

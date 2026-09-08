"use client";
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { clsx } from "@/lib/clsx";
import { Icon } from "./Icon";
import { Spinner } from "./Primitives";
import { EmojiPicker } from "./EmojiPicker";
import { markSticker } from "@/lib/emoji";

/** How long after the last keystroke the "still typing" signal stops.
 *  Slightly under the receiver's own expiry, so the indicator is refreshed
 *  rather than flickering off between words. */
const TYPING_IDLE_MS = 3000;

export function Composer({ onSend, onTyping, initialValue = "", replyTo, onCancelReply,
  disabled, error, onRetry }: {
  onSend: (text: string) => void;
  /** Called when typing starts and again when it stops. */
  onTyping?: (isTyping: boolean) => void;
  /** Prefills the box — used to edit an existing message. */
  initialValue?: string;
  replyTo?: { sender: string; content: string } | null;
  onCancelReply?: () => void;
  disabled?: boolean; error?: string | null; onRetry?: () => void;
}) {
  const [value, setValue] = useState(initialValue);
  const [sending, setSending] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  const canSend = value.trim().length > 0 && !disabled && !sending;
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  // Spans the smile button and the popover, so a click on the button to
  // close it does not also read as "outside" and reopen it.
  const pickerBox = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!pickerOpen) return;
    function onPointerDown(e: PointerEvent) {
      if (pickerBox.current && !pickerBox.current.contains(e.target as Node)) setPickerOpen(false);
    }
    function onKey(e: globalThis.KeyboardEvent) {
      if (e.key === "Escape") setPickerOpen(false);
    }
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [pickerOpen]);

  // Tracked in a ref rather than state: it changes on every keystroke and must
  // not cause a render, and the timer callback needs the current value.
  const typing = useRef(false);
  const idleTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  function stopTyping() {
    if (idleTimer.current) clearTimeout(idleTimer.current);
    idleTimer.current = null;
    if (typing.current) {
      typing.current = false;
      onTyping?.(false);
    }
  }

  function noteTyping() {
    if (!typing.current) {
      typing.current = true;
      onTyping?.(true);
    }
    if (idleTimer.current) clearTimeout(idleTimer.current);
    idleTimer.current = setTimeout(stopTyping, TYPING_IDLE_MS);
  }

  // Leaving the conversation, or the page, must clear the indicator for
  // everyone else -- otherwise it hangs there until their own timeout. The
  // cleanup is read through a ref so the effect captures nothing from the
  // render and genuinely runs once, on unmount.
  const cleanup = useRef(stopTyping);
  cleanup.current = stopTyping;
  useEffect(() => () => cleanup.current(), []);

  async function submit(e?: FormEvent) {
    e?.preventDefault();
    if (!canSend) return;
    setSending(true);
    stopTyping();
    onSend(value.trim());
    setValue("");
    setSending(false);
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void submit(); }
    if (e.key === "Escape" && onCancelReply) onCancelReply();
  }

  /** Insert at the caret rather than appending, so picking an emoji mid-word
   *  lands where the person was actually typing. */
  function insertEmoji(emoji: string) {
    const el = textareaRef.current;
    const start = el?.selectionStart ?? value.length;
    const end = el?.selectionEnd ?? value.length;
    setValue(value.slice(0, start) + emoji + value.slice(end));
    noteTyping();
    // The caret restore has to wait for the value above to reach the DOM.
    requestAnimationFrame(() => {
      const caret = start + emoji.length;
      el?.focus();
      el?.setSelectionRange(caret, caret);
    });
  }

  /** A sticker is the whole message: send it as-is rather than dropping it
   *  into whatever was already being typed. */
  function sendSticker(sticker: string) {
    if (disabled || sending) return;
    setPickerOpen(false);
    stopTyping();
    onSend(markSticker(sticker));
  }

  return (
    <form onSubmit={submit}
      className={clsx("border-t border-line bg-surface px-lg pb-lg pt-md md:px-xl", disabled && "opacity-60")}>
      {error && (
        <div role="alert" className="mb-sm flex items-center gap-sm rounded-md px-md py-sm
          text-sm font-medium" style={{ background: "#FBE3E3", color: "#B32B2B" }}>
          <Icon name="warn" size={16} strokeWidth={1.8} />
          <span className="flex-1">{error}</span>
          {onRetry && <button type="button" onClick={onRetry} className="font-semibold underline">Retry</button>}
        </div>
      )}
      {replyTo && (
        <div className="mb-sm flex items-center gap-[10px] rounded-md border-l-[3px] border-accent
          bg-hover px-md py-sm">
          <div className="flex min-w-0 flex-1 flex-col">
            <span className="text-sm font-semibold text-accent">Replying to {replyTo.sender}</span>
            <span className="truncate text-sm text-ink-muted">{replyTo.content}</span>
          </div>
          <button type="button" onClick={onCancelReply} aria-label="Cancel reply"
            className="text-ink-faint hover:text-ink"><Icon name="close" size={16} /></button>
        </div>
      )}
      <div className="flex items-end gap-[10px]">
        <div className="flex min-h-11 flex-1 items-end gap-[10px] rounded-[22px] border border-line
          bg-hover px-lg py-[9px] focus-within:border-line-focus">
          <label htmlFor="composer" className="sr-only">Message</label>
          <textarea id="composer" ref={textareaRef} rows={1} value={value} disabled={disabled}
            onChange={(e) => { setValue(e.target.value); noteTyping(); }} onKeyDown={onKeyDown}
            placeholder="Message"
            className="max-h-[120px] flex-1 resize-none bg-transparent text-base outline-none
              placeholder:text-ink-faint focus-visible:!outline-none" />
          <button type="button" aria-label="Attach a file"
            className="text-ink-faint hover:text-ink"><Icon name="clip" size={19} /></button>
          <div className="relative" ref={pickerBox}>
            <button type="button" aria-label="Insert emoji" aria-expanded={pickerOpen}
              onClick={() => setPickerOpen((open) => !open)}
              className="text-ink-faint hover:text-ink"><Icon name="smile" size={19} /></button>
            {pickerOpen && <EmojiPicker onPickEmoji={insertEmoji} onPickSticker={sendSticker} />}
          </div>
        </div>
        <button type="submit" disabled={!canSend} aria-label="Send message"
          className={clsx("inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-full transition-colors",
            canSend ? "bg-accent text-white hover:bg-accent-hover" : "bg-hover text-ink-faint")}>
          {sending ? <Spinner /> : <Icon name="send" size={19} strokeWidth={1.8} />}
        </button>
      </div>
    </form>
  );
}

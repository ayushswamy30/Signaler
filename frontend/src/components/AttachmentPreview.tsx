"use client";
import { useEffect, useState } from "react";
import { attachmentProblem, formatBytes, isImage } from "@/lib/attachment";
import { Icon } from "./Icon";
import { Button } from "./Primitives";
import { Modal } from "./Modal";

/** How much of a text file to show -- enough to recognise it, without
 *  reading a whole large file into the page just to preview it. */
const TEXT_EXCERPT_BYTES = 4096;

type PreviewKind = "image" | "video" | "audio" | "pdf" | "text" | "other";

/** What the browser can actually show of this file. Word, Excel and zip files
 *  have no in-browser rendering, so they stay a plain file card -- the same
 *  as Telegram and WhatsApp Web. */
function previewKind(file: File): PreviewKind {
  if (isImage(file.type)) return "image";
  if (file.type.startsWith("video/")) return "video";
  if (file.type.startsWith("audio/")) return "audio";
  if (file.type === "application/pdf") return "pdf";
  if (file.type === "text/plain") return "text";
  return "other";
}

/** Most phone browsers can't show a PDF inline, and an <object> for one leaves
 *  a tall empty box rather than falling back cleanly -- so ask up front.
 *  Browsers that don't report it (undefined) are given the benefit of the doubt. */
function canEmbedPdf(): boolean {
  return typeof navigator === "undefined" || navigator.pdfViewerEnabled !== false;
}

/** The last look at a chosen file before it goes out: nothing has been
 *  uploaded yet, so cancelling costs nothing and leaves nothing on the server. */
export function AttachmentPreview({ file, uploading, error, onSend, onCancel }: {
  file: File | null;
  uploading: boolean;
  /** Why the last attempt to send failed -- shown here, since this is where the person is looking. */
  error: string | null;
  onSend: () => void;
  onCancel: () => void;
}) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const [excerpt, setExcerpt] = useState<string | null>(null);
  // Set when the browser can't decode the file (an odd codec, a corrupt
  // image): a dead player or broken-image icon is worse than the plain card.
  const [mediaFailed, setMediaFailed] = useState(false);
  const kind = file ? previewKind(file) : "other";
  const embedPdf = kind === "pdf" && canEmbedPdf();
  const problem = file ? attachmentProblem(file) : null;
  const blocked = problem !== null;

  // A blob URL holds the whole file in memory until it is revoked, so it is
  // created per file and released as soon as that file is no longer shown.
  useEffect(() => {
    setMediaFailed(false);
    if (!file || !["image", "video", "audio", "pdf"].includes(kind)) { setObjectUrl(null); return; }
    const url = URL.createObjectURL(file);
    setObjectUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file, kind]);

  useEffect(() => {
    if (!file || kind !== "text") { setExcerpt(null); return; }
    let stale = false;
    void file.slice(0, TEXT_EXCERPT_BYTES).text().then((text) => {
      if (!stale) setExcerpt(file.size > TEXT_EXCERPT_BYTES ? `${text}…` : text);
    });
    return () => { stale = true; };
  }, [file, kind]);

  // The dialog itself holds focus, so Enter would otherwise do nothing.
  // Anything that uses Enter itself is left alone: Enter on Cancel must
  // cancel, and on a video's or PDF's own controls it must not send the file.
  useEffect(() => {
    if (!file) return;
    function onKey(e: KeyboardEvent) {
      if (e.key !== "Enter" || e.shiftKey || uploading || blocked) return;
      if ((e.target as HTMLElement | null)?.closest("button, a, video, audio, object, input, textarea, select")) return;
      e.preventDefault();
      onSend();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [file, uploading, blocked, onSend]);

  return (
    <Modal
      open={file !== null}
      // Closing mid-upload would look like a cancel while the file still lands in the chat.
      onClose={() => { if (!uploading) onCancel(); }}
      title="Send attachment"
      width={embedPdf ? 560 : 420}
      footer={
        <>
          <Button variant="secondary" disabled={uploading} onClick={onCancel}>Cancel</Button>
          <Button loading={uploading} disabled={blocked} onClick={onSend}>Send</Button>
        </>
      }
    >
      {file && (
        <div className="flex flex-col gap-md pb-md">
          {kind === "image" && objectUrl && !mediaFailed ? (
            <div className="flex max-h-[45vh] items-center justify-center overflow-hidden rounded-lg bg-hover">
              {/* eslint-disable-next-line @next/next/no-img-element -- a local blob URL, not an optimizable asset */}
              <img src={objectUrl} alt={`Preview of ${file.name}`} onError={() => setMediaFailed(true)}
                className="max-h-[45vh] max-w-full object-contain" />
            </div>
          ) : kind === "video" && objectUrl && !mediaFailed ? (
            <video src={objectUrl} controls preload="metadata" aria-label={`Preview of ${file.name}`}
              onError={() => setMediaFailed(true)}
              className="max-h-[45vh] w-full rounded-lg bg-black" />
          ) : kind === "audio" && objectUrl && !mediaFailed ? (
            <div className="flex flex-col items-center gap-md rounded-lg bg-hover px-lg py-xl">
              <Icon name="clip" size={28} className="text-ink-muted" />
              <audio src={objectUrl} controls preload="metadata" aria-label={`Preview of ${file.name}`}
                onError={() => setMediaFailed(true)} className="w-full" />
            </div>
          ) : embedPdf && objectUrl ? (
            <object data={objectUrl} type="application/pdf" aria-label={`Preview of ${file.name}`}
              className="h-[45vh] w-full rounded-lg bg-hover">
              <FileCard file={file} />
            </object>
          ) : kind === "text" && excerpt ? (
            <pre aria-label={`Preview of ${file.name}`} className="max-h-[45vh] overflow-auto whitespace-pre-wrap
              break-words rounded-lg bg-hover p-md text-sm">{excerpt}</pre>
          ) : (
            <FileCard file={file} />
          )}
          <div className="flex min-w-0 flex-col">
            <span className="truncate text-md font-medium">{file.name}</span>
            <span className="text-sm text-ink-muted">{formatBytes(file.size)}</span>
          </div>
          {(problem ?? error) && (
            <p role="alert" className="flex items-center gap-[5px] text-sm text-ink-danger">
              <Icon name="warn" size={13} strokeWidth={2} />{problem ?? error}
            </p>
          )}
        </div>
      )}
    </Modal>
  );
}

/** For files the browser cannot render: the extension is the best hint there is. */
function FileCard({ file }: { file: File }) {
  return (
    <div className="flex flex-col items-center gap-sm rounded-lg bg-hover px-lg py-2xl text-ink-muted">
      <Icon name="clip" size={36} />
      <span className="text-sm font-medium uppercase tracking-wide">
        {file.name.includes(".") ? file.name.split(".").pop() : "file"}
      </span>
    </div>
  );
}

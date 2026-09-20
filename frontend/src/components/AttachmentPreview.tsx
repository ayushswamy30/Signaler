"use client";
import { useEffect, useState } from "react";
import { formatBytes, isImage } from "@/lib/attachment";
import { Icon } from "./Icon";
import { Button } from "./Primitives";
import { Modal } from "./Modal";

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
  const [imageUrl, setImageUrl] = useState<string | null>(null);

  // A blob URL holds the whole file in memory until it is revoked, so it is
  // created per file and released as soon as that file is no longer shown.
  useEffect(() => {
    if (!file || !isImage(file.type)) { setImageUrl(null); return; }
    const url = URL.createObjectURL(file);
    setImageUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  // The dialog itself holds focus, so Enter would otherwise do nothing; a
  // focused button is left alone so Enter on Cancel still cancels.
  useEffect(() => {
    if (!file) return;
    function onKey(e: KeyboardEvent) {
      if (e.key !== "Enter" || e.shiftKey || uploading) return;
      if ((e.target as HTMLElement | null)?.closest("button")) return;
      e.preventDefault();
      onSend();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [file, uploading, onSend]);

  return (
    <Modal
      open={file !== null}
      // Closing mid-upload would look like a cancel while the file still lands in the chat.
      onClose={() => { if (!uploading) onCancel(); }}
      title="Send attachment"
      width={420}
      footer={
        <>
          <Button variant="secondary" disabled={uploading} onClick={onCancel}>Cancel</Button>
          <Button loading={uploading} onClick={onSend}>Send</Button>
        </>
      }
    >
      {file && (
        <div className="flex flex-col gap-md pb-md">
          {imageUrl ? (
            <div className="flex max-h-[45vh] items-center justify-center overflow-hidden rounded-lg bg-hover">
              {/* eslint-disable-next-line @next/next/no-img-element -- a local blob URL, not an optimizable asset */}
              <img src={imageUrl} alt={`Preview of ${file.name}`}
                className="max-h-[45vh] max-w-full object-contain" />
            </div>
          ) : (
            <div className="flex flex-col items-center gap-sm rounded-lg bg-hover px-lg py-2xl text-ink-muted">
              <Icon name="clip" size={36} />
              <span className="text-sm font-medium uppercase tracking-wide">
                {file.name.includes(".") ? file.name.split(".").pop() : "file"}
              </span>
            </div>
          )}
          <div className="flex min-w-0 flex-col">
            <span className="truncate text-md font-medium">{file.name}</span>
            <span className="text-sm text-ink-muted">{formatBytes(file.size)}</span>
          </div>
          {error && (
            <p role="alert" className="flex items-center gap-[5px] text-sm text-ink-danger">
              <Icon name="warn" size={13} strokeWidth={2} />{error}
            </p>
          )}
        </div>
      )}
    </Modal>
  );
}

"use client";

/** The right-hand panel: who is in a conversation, and what you may do about it.
 *
 *  Group management lives here rather than in a separate screen because every
 *  action — rename, add, remove, promote, leave — is about the membership
 *  already on display. Admin-only controls are hidden rather than disabled: a
 *  member has no way to become an admin from this panel, so showing a greyed-out
 *  button would only be a dead end. */

import { useState } from "react";
import { clsx } from "@/lib/clsx";
import { counterpart, formatLastSeen, title } from "@/lib/format";
import type { Conversation, Me, Participant } from "@/lib/types";
import { Icon } from "./Icon";
import { Avatar, Button, Chip, Field } from "./Primitives";
import { NewGroupModal } from "./NewGroupModal";

export function ConversationInfo({
  conversation,
  me,
  onClose,
  onRename,
  onAddMembers,
  onRemoveMember,
  onSetRole,
  onLeave,
  onToggleMute,
}: {
  conversation: Conversation;
  me: Me;
  onClose: () => void;
  onRename: (name: string) => void;
  onAddMembers: (memberIds: number[]) => Promise<unknown> | void;
  onRemoveMember: (memberId: number) => void;
  onSetRole: (memberId: number, role: "admin" | "member") => void;
  onLeave: () => void;
  onToggleMute: () => void;
}) {
  const isGroup = conversation.type === "group";
  const iAmAdmin = conversation.myRole === "admin";
  const other = counterpart(conversation, me.id);

  const [renaming, setRenaming] = useState(false);
  const [draftName, setDraftName] = useState(conversation.name ?? "");
  const [adding, setAdding] = useState(false);
  const [confirmLeave, setConfirmLeave] = useState(false);

  function saveName() {
    const name = draftName.trim();
    if (name && name !== conversation.name) onRename(name);
    setRenaming(false);
  }

  return (
    <aside
      aria-label={isGroup ? "Group info" : "Contact info"}
      className="flex w-full shrink-0 flex-col overflow-y-auto border-l border-line bg-surface
        lg:w-[360px]"
    >
      <div className="flex items-center gap-md border-b border-line-subtle px-lg py-md">
        <h2 className="flex-1 text-lg font-semibold">{isGroup ? "Group info" : "Contact info"}</h2>
        <button onClick={onClose} aria-label="Close panel" className="text-ink-faint hover:text-ink">
          <Icon name="close" size={18} />
        </button>
      </div>

      <div className="flex flex-col items-center gap-[10px] border-b border-line-subtle px-lg py-xl">
        <Avatar name={title(conversation, me.id)} size={84} />
        {renaming ? (
          <div className="flex w-full flex-col gap-sm">
            <Field
              id="group-rename"
              label="Group name"
              value={draftName}
              maxLength={100}
              onChange={(event) => setDraftName(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") saveName();
                if (event.key === "Escape") setRenaming(false);
              }}
            />
            <div className="flex justify-end gap-sm">
              <Button variant="secondary" onClick={() => setRenaming(false)}>Cancel</Button>
              <Button onClick={saveName}>Save</Button>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-[3px]">
            <p className="text-xl font-semibold">{title(conversation, me.id)}</p>
            <p className="text-md text-ink-muted">
              {isGroup
                ? `${conversation.participants.length} members`
                : other
                  ? `@${other.username}`
                  : ""}
            </p>
            {!isGroup && other?.about && (
              <p className="max-w-[280px] text-center text-md text-ink-muted">{other.about}</p>
            )}
            {!isGroup && other && !other.isOnline && (
              <p className="text-sm text-ink-faint">
                {formatLastSeen(other.lastSeen)
                  ? `Last seen ${formatLastSeen(other.lastSeen)}`
                  : "Offline"}
              </p>
            )}
          </div>
        )}

        {isGroup && iAmAdmin && !renaming && (
          <div className="flex gap-sm">
            <Button variant="secondary" onClick={() => { setDraftName(conversation.name ?? ""); setRenaming(true); }}>
              Rename
            </Button>
            <Button variant="secondary" onClick={() => setAdding(true)}>Add member</Button>
          </div>
        )}
      </div>

      <button
        onClick={onToggleMute}
        className="flex items-center gap-md border-b border-line-subtle px-lg py-md text-left
          hover:bg-hover"
      >
        <Icon name={conversation.muted ? "mute" : "bell"} size={18} className="text-ink-muted" />
        <span className="flex flex-1 flex-col">
          <span className="text-base font-medium">
            {conversation.muted ? "Notifications muted" : "Notifications on"}
          </span>
          <span className="text-sm text-ink-faint">
            {conversation.muted ? "Tap to unmute this conversation" : "Tap to mute this conversation"}
          </span>
        </span>
      </button>

      {isGroup && (
        <div className="flex flex-col gap-[2px] p-sm">
          <p className="px-md pb-sm pt-md text-xs font-semibold tracking-wide text-ink-faint">
            MEMBERS · {conversation.participants.length}
          </p>
          {conversation.participants.map((participant) => (
            <MemberRow
              key={participant.user.id}
              participant={participant}
              isMe={participant.user.id === me.id}
              canManage={iAmAdmin && participant.user.id !== me.id}
              onRemove={() => onRemoveMember(participant.user.id)}
              onSetRole={(role) => onSetRole(participant.user.id, role)}
            />
          ))}
        </div>
      )}

      <div className="mt-auto border-t border-line-subtle p-sm">
        {confirmLeave ? (
          <div className="flex flex-col gap-sm p-md">
            <p className="text-md text-ink-muted">
              {conversation.participants.length === 1
                ? "You are the last member, so leaving deletes this group and its messages."
                : "You will stop receiving messages from this group."}
            </p>
            <div className="flex justify-end gap-sm">
              <Button variant="secondary" onClick={() => setConfirmLeave(false)}>Cancel</Button>
              <Button variant="danger" onClick={onLeave}>Leave group</Button>
            </div>
          </div>
        ) : isGroup ? (
          <button
            onClick={() => setConfirmLeave(true)}
            className="flex w-full items-center gap-md rounded-lg p-[11px_12px] text-ink-danger
              hover:bg-hover"
          >
            <Icon name="close" size={18} />
            <span className="text-base font-medium">Leave group</span>
          </button>
        ) : null}
      </div>

      <NewGroupModal
        open={adding}
        onClose={() => setAdding(false)}
        mode="add"
        excludeIds={conversation.participants.map((p) => p.user.id)}
        onSubmit={({ memberIds }) => onAddMembers(memberIds)}
      />
    </aside>
  );
}

function MemberRow({
  participant,
  isMe,
  canManage,
  onRemove,
  onSetRole,
}: {
  participant: Participant;
  isMe: boolean;
  canManage: boolean;
  onRemove: () => void;
  onSetRole: (role: "admin" | "member") => void;
}) {
  const [open, setOpen] = useState(false);
  const isAdmin = participant.role === "admin";

  return (
    <div className="relative flex items-center gap-md rounded-lg p-[9px_12px] hover:bg-hover">
      <Avatar name={participant.user.displayName} size={38} online={participant.user.isOnline} />
      <div className="flex min-w-0 flex-1 flex-col">
        <span className="truncate text-base font-medium">
          {participant.user.displayName}
          {isMe && <span className="text-ink-faint"> (you)</span>}
        </span>
        <span className="truncate text-sm text-ink-faint">@{participant.user.username}</span>
      </div>
      {isAdmin && <Chip tone="accent">Admin</Chip>}
      {canManage && (
        <button
          onClick={() => setOpen((value) => !value)}
          aria-label={`Manage ${participant.user.displayName}`}
          aria-expanded={open}
          className="text-ink-faint hover:text-ink"
        >
          <Icon name="more" size={18} />
        </button>
      )}
      {open && (
        <div
          className="absolute right-md top-[46px] z-10 flex w-[200px] flex-col overflow-hidden
            rounded-lg border border-line bg-raised py-xs shadow-md"
          role="menu"
        >
          <MenuItem
            onClick={() => { onSetRole(isAdmin ? "member" : "admin"); setOpen(false); }}
          >
            {isAdmin ? "Dismiss as admin" : "Make admin"}
          </MenuItem>
          <MenuItem danger onClick={() => { onRemove(); setOpen(false); }}>
            Remove from group
          </MenuItem>
        </div>
      )}
    </div>
  );
}

function MenuItem({
  children,
  onClick,
  danger = false,
}: {
  children: React.ReactNode;
  onClick: () => void;
  danger?: boolean;
}) {
  return (
    <button
      role="menuitem"
      onClick={onClick}
      className={clsx(
        "px-md py-sm text-left text-md hover:bg-hover",
        danger ? "text-ink-danger" : "text-ink",
      )}
    >
      {children}
    </button>
  );
}

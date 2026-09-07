"use client";

/** Create a group, or add people to one.
 *
 *  Both are the same interaction — pick several people — so one component
 *  serves both, with `mode` deciding whether a name is asked for. */

import { useState } from "react";
import type { User } from "@/lib/types";
import { Avatar, Button, Field } from "./Primitives";
import { Icon } from "./Icon";
import { Modal } from "./Modal";
import { PeopleList, PeopleSearchField, usePeopleSearch } from "./PeoplePicker";

export function NewGroupModal({
  open,
  onClose,
  onSubmit,
  mode = "create",
  excludeIds = [],
}: {
  open: boolean;
  onClose: () => void;
  onSubmit: (input: { name: string; memberIds: number[] }) => Promise<unknown> | void;
  mode?: "create" | "add";
  /** People already in the group, so they are not offered again. */
  excludeIds?: number[];
}) {
  const { query, setQuery, people, searching } = usePeopleSearch(excludeIds);
  const [selected, setSelected] = useState<User[]>([]);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);

  const creating = mode === "create";
  const ready = selected.length > 0 && (!creating || name.trim().length > 0);

  function toggle(user: User) {
    setSelected((current) =>
      current.some((u) => u.id === user.id)
        ? current.filter((u) => u.id !== user.id)
        : [...current, user],
    );
  }

  function reset() {
    setSelected([]);
    setName("");
    setQuery("");
  }

  async function submit() {
    if (!ready || busy) return;
    setBusy(true);
    try {
      await onSubmit({ name: name.trim(), memberIds: selected.map((u) => u.id) });
      reset();
      onClose();
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={creating ? "New group" : "Add members"}
      subtitle={
        creating
          ? "Name the group and choose who is in it. You will be its admin."
          : "Choose who to add. Everyone in the group will be told."
      }
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button disabled={!ready} loading={busy} onClick={submit}>
            {creating ? "Create group" : `Add ${selected.length || ""}`.trim()}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-lg">
        {creating && (
          <Field
            id="group-name"
            label="Group name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Design Guild"
            maxLength={100}
          />
        )}

        {selected.length > 0 && (
          <ul className="flex flex-wrap gap-sm" aria-label="Selected people">
            {selected.map((user) => (
              <li key={user.id}>
                <button
                  type="button"
                  onClick={() => toggle(user)}
                  aria-label={`Remove ${user.displayName}`}
                  className="flex items-center gap-sm rounded-full bg-hover py-[3px] pl-[3px] pr-md
                    text-sm font-medium hover:bg-active"
                >
                  <Avatar name={user.displayName} size={24} />
                  {user.displayName}
                  <Icon name="close" size={13} className="text-ink-faint" />
                </button>
              </li>
            ))}
          </ul>
        )}

        <PeopleSearchField value={query} onChange={setQuery} />
        <PeopleList
          people={people}
          selectedIds={selected.map((u) => u.id)}
          onToggle={toggle}
          multiple
          searching={searching}
          query={query}
          emptyBody={
            creating
              ? "Search for someone by username to add them to the group."
              : "Everyone you can add is already in this group."
          }
        />
      </div>
    </Modal>
  );
}

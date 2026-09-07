"use client";

import { useState } from "react";
import type { User } from "@/lib/types";
import { Button } from "./Primitives";
import { Modal } from "./Modal";
import { PeopleList, PeopleSearchField, usePeopleSearch } from "./PeoplePicker";

export function NewMessageModal({ open, onClose, onStart }: {
  open: boolean;
  onClose: () => void;
  onStart: (user: User) => void;
}) {
  const { query, setQuery, people, searching } = usePeopleSearch();
  const [selected, setSelected] = useState<User | null>(null);

  function start() {
    if (!selected) return;
    onStart(selected);
    setSelected(null);
    setQuery("");
    onClose();
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="New message"
      subtitle="Pick a contact, or search for anyone by username."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button disabled={!selected} onClick={start}>Start chat</Button>
        </>
      }
    >
      <div className="flex flex-col gap-lg">
        <PeopleSearchField value={query} onChange={setQuery} />
        <PeopleList
          people={people}
          selectedIds={selected ? [selected.id] : []}
          onToggle={(user) => setSelected((current) => (current?.id === user.id ? null : user))}
          searching={searching}
          query={query}
        />
      </div>
    </Modal>
  );
}

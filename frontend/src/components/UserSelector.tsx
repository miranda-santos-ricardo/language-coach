import { useState } from "react";
import type { ChangeEvent, FormEvent } from "react";

import type { User } from "../api/types";

interface UserSelectorProps {
  users: User[];
  selectedUserId: string | null;
  loading: boolean;
  onSelect: (user: User) => void;
  onCreate: (displayName: string) => Promise<void>;
}

export function UserSelector({
  users,
  selectedUserId,
  loading,
  onSelect,
  onCreate,
}: UserSelectorProps) {
  const [displayName, setDisplayName] = useState("");
  const [creating, setCreating] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = displayName.trim();
    if (!value) return;

    setCreating(true);
    try {
      await onCreate(value);
      setDisplayName("");
    } finally {
      setCreating(false);
    }
  }

  return (
    <section className="panel" aria-labelledby="user-selector-title">
      <div className="panel__header">
        <div>
          <p className="eyebrow">Practice profile</p>
          <h2 id="user-selector-title">Who&apos;s practicing?</h2>
        </div>
      </div>

      {loading ? (
        <p className="muted">Loading users…</p>
      ) : users.length === 0 ? (
        <p className="muted">Create the first user to begin.</p>
      ) : (
        <div className="user-list" role="list" aria-label="Users">
          {users.map((user) => (
            <div role="listitem" key={user.id}>
              <button
                type="button"
                className={
                  user.id === selectedUserId ? "user-chip user-chip--active" : "user-chip"
                }
                onClick={() => onSelect(user)}
                aria-pressed={user.id === selectedUserId}
              >
                <span className="user-chip__avatar" aria-hidden="true">
                  {user.display_name.slice(0, 1).toUpperCase()}
                </span>
                <span>{user.display_name}</span>
              </button>
            </div>
          ))}
        </div>
      )}

      <form className="inline-form" onSubmit={handleSubmit}>
        <label htmlFor="new-user-name">Add user</label>
        <div className="inline-form__row">
          <input
            id="new-user-name"
            value={displayName}
            onChange={(event: ChangeEvent<HTMLInputElement>) => setDisplayName(event.target.value)}
            placeholder="Display name"
            maxLength={120}
          />
          <button className="button button--secondary" type="submit" disabled={creating}>
            {creating ? "Adding…" : "+ Add user"}
          </button>
        </div>
      </form>
    </section>
  );
}

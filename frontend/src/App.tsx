import { useEffect, useState } from "react";

import { api } from "./api/client";
import type { LanguageProfile, User, PracticeSession} from "./api/types";
import { BackendStatus } from "./components/BackendStatus";
import { LanguageProfileCard } from "./components/LanguageProfileCard";
import { LanguageProfileForm } from "./components/LanguageProfileForm";
import { UserSelector } from "./components/UserSelector";

import { PracticeSessionForm } from "./components/PracticeSessionForm";
import { PracticeSessionStarted } from "./components/PracticeSessionStarted";

export default function App() {
  const [backendStatus, setBackendStatus] = useState<"checking" | "online" | "offline">(
    "checking",
  );
  const [users, setUsers] = useState<User[]>([]);
  const [usersLoading, setUsersLoading] = useState(true);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [profiles, setProfiles] = useState<LanguageProfile[]>([]);
  const [profilesLoading, setProfilesLoading] = useState(false);
  const [editingProfile, setEditingProfile] = useState<LanguageProfile | null>(null);
  const [creatingProfile, setCreatingProfile] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [practicingProfile, setPracticingProfile] =useState<LanguageProfile | null>(null);
  const [activeSession, setActiveSession] = useState<PracticeSession | null>(null);

  useEffect(() => {
    void api
      .health()
      .then(() => setBackendStatus("online"))
      .catch(() => setBackendStatus("offline"));

    void loadUsers();
  }, []);

  async function loadUsers() {
    setUsersLoading(true);
    setError(null);
    try {
      const rows = await api.listUsers();
      setUsers(rows);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load users");
    } finally {
      setUsersLoading(false);
    }
  }

  async function selectUser(user: User) {
    setSelectedUser(user);
    setEditingProfile(null);
    setCreatingProfile(false);
    setProfilesLoading(true);
    setError(null);
    setPracticingProfile(null);
    setActiveSession(null);
    try {
      setProfiles(await api.listProfiles(user.id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load language profiles");
      setProfiles([]);
    } finally {
      setProfilesLoading(false);
    }
  }

  async function createUser(displayName: string) {
    setError(null);
    try {
      const created = await api.createUser(displayName);
      setUsers((current) => [...current, created]);
      await selectUser(created);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to create user");
      throw reason;
    }
  }

  function handleProfileSaved(saved: LanguageProfile) {
    setProfiles((current) => {
      const exists = current.some((profile) => profile.id === saved.id);
      return exists
        ? current.map((profile) => (profile.id === saved.id ? saved : profile))
        : [...current, saved];
    });
    setEditingProfile(null);
    setCreatingProfile(false);
  }

  function startPractice(profile: LanguageProfile) {
    setEditingProfile(null);
    setCreatingProfile(false);
    setActiveSession(null);
    setPracticingProfile(profile);
  }

  function handleSessionStarted(
    session: PracticeSession,
  ) {
    setActiveSession(session);
  }

  const showProfileForm = selectedUser && (creatingProfile || editingProfile);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">AI Language & Professional Communication Coach</p>
          <h1>Build the language you want to use.</h1>
          <p className="app-header__subtitle">
            Build your language baseline and choose what you want to practice today.
          </p>
        </div>
        <BackendStatus status={backendStatus} />
      </header>

      {error && <div className="alert alert--error">{error}</div>}

      <main className="app-grid">
        <UserSelector
          users={users}
          selectedUserId={selectedUser?.id ?? null}
          loading={usersLoading}
          onSelect={(user) => void selectUser(user)}
          onCreate={createUser}
        />

        <section className="workspace" aria-live="polite">
          {!selectedUser ? (
            <div className="empty-state panel">
              <p className="eyebrow">Languages</p>
              <h2>Select a user</h2>
              <p>Choose who is practicing to view and configure their language profiles.</p>
            </div>
          ) : practicingProfile && activeSession ? (
            <PracticeSessionStarted
              profile={practicingProfile}
              session={activeSession}
              onBack={() => {
                setPracticingProfile(null);
                setActiveSession(null);
              }}
            />
          ) : practicingProfile ? (
            <PracticeSessionForm
              userId={selectedUser.id}
              profile={practicingProfile}
              onStarted={handleSessionStarted}
              onCancel={() => setPracticingProfile(null)}
            />
          ) : showProfileForm ? (
            <LanguageProfileForm
              userId={selectedUser.id}
              profile={editingProfile ?? undefined}
              onSaved={handleProfileSaved}
              onCancel={() => {
                setEditingProfile(null);
                setCreatingProfile(false);
              }}
            />
          ) : (
            <section className="panel" aria-labelledby="language-profiles-title">
              <div className="panel__header">
                <div>
                  <p className="eyebrow">{selectedUser.display_name}</p>
                  <h2 id="language-profiles-title">Languages</h2>
                </div>
                <button
                  type="button"
                  className="button button--primary"
                  onClick={() => setCreatingProfile(true)}
                >
                  + Add language
                </button>
              </div>

              {profilesLoading ? (
                <p className="muted">Loading language profiles…</p>
              ) : profiles.length === 0 ? (
                <div className="empty-state empty-state--compact">
                  <h3>No language profiles yet</h3>
                  <p>Add the first language baseline for {selectedUser.display_name}.</p>
                </div>
              ) : (
                <div className="profile-grid">
                  {profiles.map((profile) => (
                    <LanguageProfileCard
                      profile={profile}
                      onEdit={(profile) => setEditingProfile(profile)}
                      onStartPractice={startPractice}
                      key={profile.id}
                    />
                  ))}
                </div>
              )}
            </section>
          )}
        </section>
      </main>
    </div>
  );
}

"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { getIdToken, onAuthChange, signInWithGoogle, signOutGoogle } from "@/lib/auth";

type Setting = {
  key: string;
  env: string;
  label: string;
  kind: "int" | "bool";
  unit: string;
  value: number | boolean;
  default: number | boolean;
  minimum: number | null;
  maximum: number | null;
  overridden: boolean;
};

type GodUser = { email: string; role: "god" | "admin" };

type LoggedInUser = { email: string; nickname: string | null; role: string | null };

type GodStatus = {
  authMode: "emulator" | "google";
  geminiConfigured: boolean;
  telegramConfigured: boolean;
  specialUsers: number;
  overriddenSettings: number;
  geminiUsage: {
    lastHour: number;
    lastDay: number;
    maxPerHour: number;
    maxPerDay: number;
  };
  audit: { time: string; action: string; detail: Record<string, unknown> }[];
};

export default function GodPage() {
  const base = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

  const [token, setToken] = useState<string | null>(null);
  const [unlocked, setUnlocked] = useState(false);
  const [signingIn, setSigningIn] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [settings, setSettings] = useState<Setting[]>([]);
  const [draft, setDraft] = useState<Record<string, string | boolean>>({});
  const [users, setUsers] = useState<GodUser[]>([]);
  const [allUsers, setAllUsers] = useState<LoggedInUser[]>([]);
  const [status, setStatus] = useState<GodStatus | null>(null);

  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [newEmail, setNewEmail] = useState("");
  const [newRole, setNewRole] = useState<"god" | "admin">("admin");
  const [userMessage, setUserMessage] = useState<string | null>(null);

  const applySettings = useCallback((items: Setting[]) => {
    setSettings(items);
    setDraft(
      Object.fromEntries(
        items.map((item) => [
          item.key,
          item.kind === "bool" ? Boolean(item.value) : String(item.value),
        ]),
      ),
    );
  }, []);

  const authHeaders = useCallback(
    (candidate?: string) => ({
      Authorization: `Bearer ${candidate ?? token ?? ""}`,
    }),
    [token],
  );

  const loadAll = useCallback(
    async (candidate: string) => {
      const headers = authHeaders(candidate);
      const [settingsRes, usersRes, statusRes, allUsersRes] = await Promise.all([
        fetch(`${base}/god/settings`, { headers }),
        fetch(`${base}/god/users`, { headers }),
        fetch(`${base}/god/status`, { headers }),
        fetch(`${base}/god/users/all`, { headers }),
      ]);
      if (!settingsRes.ok || !usersRes.ok || !statusRes.ok || !allUsersRes.ok) {
        throw new Error("Could not load GOD data");
      }
      applySettings((await settingsRes.json()).settings as Setting[]);
      setUsers((await usersRes.json()).users as GodUser[]);
      setStatus((await statusRes.json()) as GodStatus);
      setAllUsers((await allUsersRes.json()).users as LoggedInUser[]);
    },
    [applySettings, authHeaders, base],
  );

  const unlock = useCallback(
    async (candidate: string) => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`${base}/god/me`, {
          headers: authHeaders(candidate),
        });
        if (!res.ok) {
          setError(
            res.status === 401
              ? "Sign in with Google first."
              : "This account is not GOD.",
          );
          return;
        }
        setToken(candidate);
        setUnlocked(true);
        await loadAll(candidate);
      } catch {
        setError("Network error while unlocking.");
      } finally {
        setLoading(false);
      }
    },
    [authHeaders, base, loadAll],
  );

  const doSignIn = async () => {
    setSigningIn(true);
    setError(null);
    try {
      await signInWithGoogle();
      const candidate = await getIdToken();
      if (!candidate) {
        setError("Sign-in did not return a token.");
        return;
      }
      await unlock(candidate);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Network error while signing in.",
      );
    } finally {
      setSigningIn(false);
    }
  };

  useEffect(() => {
    const unsubscribe = onAuthChange(async (user) => {
      if (user) {
        const candidate = await getIdToken();
        if (candidate) {
          await unlock(candidate);
        }
      }
    });
    return unsubscribe;
  }, [unlock]);

  const saveSettings = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token) return;
    setSaving(true);
    setSaveMessage(null);
    try {
      const values: Record<string, number | boolean> = {};
      for (const item of settings) {
        const raw = draft[item.key];
        values[item.key] = item.kind === "bool" ? Boolean(raw) : Number(raw);
      }
      const res = await fetch(`${base}/god/settings`, {
        method: "PUT",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ values }),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { detail?: string };
        setSaveMessage(body.detail ?? `Save failed (status ${res.status})`);
        return;
      }
      applySettings((await res.json()).settings as Setting[]);
      setSaveMessage("Settings saved.");
    } catch {
      setSaveMessage("Network error while saving.");
    } finally {
      setSaving(false);
    }
  };

  const resetSettings = async () => {
    if (!token) return;
    setSaving(true);
    setSaveMessage(null);
    try {
      const res = await fetch(`${base}/god/settings/reset`, {
        method: "POST",
        headers: authHeaders(),
      });
      if (!res.ok) {
        setSaveMessage(`Reset failed (status ${res.status})`);
        return;
      }
      applySettings((await res.json()).settings as Setting[]);
      setSaveMessage("Settings reset to defaults.");
    } catch {
      setSaveMessage("Network error while resetting.");
    } finally {
      setSaving(false);
    }
  };

  const addUser = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token) return;
    setUserMessage(null);
    try {
      const res = await fetch(`${base}/god/users`, {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ email: newEmail.trim(), role: newRole }),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { detail?: string };
        setUserMessage(body.detail ?? `Add failed (status ${res.status})`);
        return;
      }
      setNewEmail("");
      const usersRes = await fetch(`${base}/god/users`, { headers: authHeaders() });
      if (usersRes.ok) {
        setUsers((await usersRes.json()).users as GodUser[]);
      }
      setUserMessage("User added.");
    } catch {
      setUserMessage("Network error while adding the user.");
    }
  };

  const removeUser = async (email: string) => {
    if (!token) return;
    setUserMessage(null);
    try {
      const res = await fetch(`${base}/god/users/${encodeURIComponent(email)}`, {
        method: "DELETE",
        headers: authHeaders(),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { detail?: string };
        setUserMessage(body.detail ?? `Remove failed (status ${res.status})`);
        return;
      }
      setUsers((current) => current.filter((user) => user.email !== email));
      setUserMessage("User removed.");
    } catch {
      setUserMessage("Network error while removing the user.");
    }
  };

  const resetQuota = async () => {
    if (!token) return;
    try {
      const res = await fetch(`${base}/god/quota/reset`, {
        method: "POST",
        headers: authHeaders(),
      });
      if (!res.ok) {
        setUserMessage(`Quota reset failed (status ${res.status})`);
        return;
      }
      const body = (await res.json()) as { geminiUsage: GodStatus["geminiUsage"] };
      setStatus((current) =>
        current ? { ...current, geminiUsage: body.geminiUsage } : current,
      );
      setUserMessage("Gemini quota counters reset.");
    } catch {
      setUserMessage("Network error while resetting the quota.");
    }
  };

  const lock = async () => {
    await signOutGoogle();
    setToken(null);
    setUnlocked(false);
    setSettings([]);
    setUsers([]);
    setStatus(null);
    setSaveMessage(null);
    setUserMessage(null);
  };

  if (!unlocked) {
    return (
      <main className="mx-auto flex min-h-screen w-full max-w-3xl flex-col justify-center gap-6 p-6">
        <section className="glass flex flex-col gap-4 px-6 py-8">
          <div className="flex flex-col gap-1">
            <h1 className="brand text-3xl">GOD</h1>
            <p className="muted text-sm">
              Website superuser area. Sign in with the GOD Google account.
            </p>
          </div>
          <button
            type="button"
            onClick={() => void doSignIn()}
            disabled={signingIn || loading}
            className="btn-primary self-start"
          >
            {signingIn || loading ? "Signing in..." : "Sign in with Google"}
          </button>
          {error ? (
            <p role="alert" className="text-sm font-medium text-rose-700">
              {error}
            </p>
          ) : null}
          <Link href="/" className="text-sm text-blue-800 underline">
            Back to site
          </Link>
        </section>
      </main>
    );
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-6 p-6">
      <header className="glass flex flex-wrap items-center justify-between gap-4 px-6 py-5">
        <div className="flex flex-col gap-1">
          <h1 className="brand text-3xl">GOD</h1>
          <p className="muted text-sm">
            Runtime limits and special users. Game rules are not editable here.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link href="/" className="btn-ghost text-sm">
            Back to site
          </Link>
          <button type="button" onClick={() => void lock()} className="btn-ghost text-sm">
            Sign out
          </button>
        </div>
      </header>

      {status ? (
        <section className="glass grid gap-4 px-6 py-5 sm:grid-cols-2 lg:grid-cols-6">
          <StatusPill label="Auth" ok text={status.authMode} />
          <StatusPill label="Gemini key" ok={status.geminiConfigured} />
          <StatusPill label="Telegram" ok={status.telegramConfigured} />
          <StatusPill label="Special users" ok text={String(status.specialUsers)} />
          <StatusPill label="Changed limits" ok text={String(status.overriddenSettings)} />
          <StatusPill
            label="Gemini jobs"
            ok={status.geminiUsage.lastHour < status.geminiUsage.maxPerHour}
            text={`${status.geminiUsage.lastHour}/${status.geminiUsage.maxPerHour} hr · ${status.geminiUsage.lastDay}/${status.geminiUsage.maxPerDay} day`}
          />
        </section>
      ) : null}

      {status ? (
        <div className="flex justify-end">
          <button type="button" onClick={() => void resetQuota()} className="btn-ghost text-xs">
            Reset Gemini quota counters
          </button>
        </div>
      ) : null}

      <form onSubmit={saveSettings} className="glass flex flex-col gap-4 px-6 py-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold text-blue-900">Limits</h2>
            <p className="muted text-xs">
              Every value is validated. Missing or invalid values fall back to
              the default. Saved values survive a restart.
            </p>
          </div>
          <div className="flex gap-2">
            <button type="button" onClick={() => void resetSettings()} disabled={saving} className="btn-ghost text-sm">
              Reset defaults
            </button>
            <button type="submit" disabled={saving} className="btn-primary text-sm">
              {saving ? "Saving..." : "Save"}
            </button>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {settings.map((item) => (
            <label key={item.key} className="flex flex-col gap-1 text-start">
              <span className="flex items-center gap-2 text-sm font-medium">
                {item.label}
                {item.overridden ? (
                  <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold text-amber-800">
                    changed
                  </span>
                ) : null}
              </span>
              {item.kind === "bool" ? (
                <input
                  type="checkbox"
                  checked={Boolean(draft[item.key])}
                  onChange={(event) =>
                    setDraft((current) => ({
                      ...current,
                      [item.key]: event.target.checked,
                    }))
                  }
                  className="h-5 w-5 accent-blue-700"
                />
              ) : (
                <input
                  type="number"
                  value={String(draft[item.key] ?? "")}
                  min={item.minimum ?? undefined}
                  max={item.maximum ?? undefined}
                  onChange={(event) =>
                    setDraft((current) => ({
                      ...current,
                      [item.key]: event.target.value,
                    }))
                  }
                  className="input"
                />
              )}
              <span className="muted text-[11px]">
                {item.env}
                {item.unit ? ` · ${item.unit}` : ""} · default{" "}
                {String(item.default)}
                {item.minimum !== null && item.maximum !== null
                  ? ` · range ${item.minimum}-${item.maximum}`
                  : ""}
              </span>
            </label>
          ))}
        </div>

        {saveMessage ? (
          <p role="status" className="text-sm font-medium text-blue-900">
            {saveMessage}
          </p>
        ) : null}
      </form>

      <section className="glass flex flex-col gap-4 px-6 py-6">
        <div>
          <h2 className="text-xl font-semibold text-blue-900">Logged-in users</h2>
          <p className="muted text-xs">
            Every Google account that has signed in, with its nickname and role.
          </p>
        </div>

        {allUsers.length === 0 ? (
          <p className="muted text-sm">No one has signed in yet.</p>
        ) : (
          <div className="flex flex-col gap-2">
            {allUsers.map((user) => (
              <div
                key={user.email}
                className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-blue-100 bg-white/60 px-4 py-2"
              >
                <div className="flex items-center gap-2">
                  <span className="text-sm text-blue-900">{user.email}</span>
                  <span className="muted text-xs">
                    {user.nickname ? `(${user.nickname})` : "no nickname"}
                  </span>
                </div>
                {user.role ? (
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                      user.role === "god"
                        ? "bg-indigo-100 text-indigo-800"
                        : "bg-emerald-100 text-emerald-800"
                    }`}
                  >
                    {user.role}
                  </span>
                ) : (
                  <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">
                    player
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="glass flex flex-col gap-4 px-6 py-6">
        <div>
          <h2 className="text-xl font-semibold text-blue-900">Special users</h2>
          <p className="muted text-xs">
            GOD can manage website users. GOD cannot perform game admin actions.
          </p>
        </div>

        <div className="flex flex-col gap-2">
          {users.map((user) => (
            <div
              key={user.email}
              className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-blue-100 bg-white/60 px-4 py-2"
            >
              <div className="flex items-center gap-2">
                <span className="text-sm text-blue-900">{user.email}</span>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                    user.role === "god"
                      ? "bg-indigo-100 text-indigo-800"
                      : "bg-emerald-100 text-emerald-800"
                  }`}
                >
                  {user.role}
                </span>
              </div>
              <button
                type="button"
                onClick={() => void removeUser(user.email)}
                disabled={user.email === "tal.vazanas@gmail.com"}
                className="btn-ghost text-xs"
                title={
                  user.email === "tal.vazanas@gmail.com"
                    ? "The primary GOD account cannot be removed"
                    : "Remove user"
                }
              >
                Remove
              </button>
            </div>
          ))}
        </div>

        <form onSubmit={addUser} className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <label className="flex flex-1 flex-col gap-1 text-start">
            <span className="text-sm font-medium">Email</span>
            <input
              type="email"
              value={newEmail}
              onChange={(event) => setNewEmail(event.target.value)}
              className="input"
              placeholder="person@example.com"
              required
            />
          </label>
          <label className="flex flex-col gap-1 text-start">
            <span className="text-sm font-medium">Role</span>
            <select
              value={newRole}
              onChange={(event) => setNewRole(event.target.value as "god" | "admin")}
              className="input"
            >
              <option value="admin">admin</option>
              <option value="god">god</option>
            </select>
          </label>
          <button type="submit" className="btn-primary text-sm">
            Add user
          </button>
        </form>

        {userMessage ? (
          <p role="status" className="text-sm font-medium text-blue-900">
            {userMessage}
          </p>
        ) : null}
      </section>

      {status && status.audit.length > 0 ? (
        <section className="glass flex flex-col gap-2 px-6 py-5">
          <h2 className="text-lg font-semibold text-blue-900">Recent GOD actions</h2>
          <ul className="flex flex-col gap-1 text-xs text-blue-900/80">
            {status.audit.map((entry, index) => (
              <li key={`${entry.time}-${index}`}>
                {entry.time} · {entry.action}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </main>
  );
}

function StatusPill({
  label,
  ok,
  text,
}: {
  label: string;
  ok: boolean;
  text?: string;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="muted text-xs">{label}</span>
      <span className={`text-sm font-semibold ${ok ? "text-emerald-700" : "text-rose-700"}`}>
        {text ?? (ok ? "Ready" : "Not configured")}
      </span>
    </div>
  );
}

"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import EmptyState from "@/components/ui/EmptyState";
import ErrorMessage from "@/components/ui/ErrorMessage";
import LoadingSpinner from "@/components/ui/LoadingSpinner";
import { subscribeRooms } from "@/lib/roomsStore";
import { adminFetch, getIdToken, getProfile, onAuthChange, saveProfile, signInWithGoogle, signOutGoogle } from "@/lib/auth";
import {
  RoomSummary,
  isRoomActive,
  roomStatusLabel,
  roomStatusTone,
} from "@/utils/rooms";

function backendTone(status: "checking" | "connected" | "offline"): string {
  if (status === "connected") {
    return "border-emerald-300/70 bg-emerald-100/70 text-emerald-800";
  }
  if (status === "offline") {
    return "border-rose-300/70 bg-rose-100/70 text-rose-800";
  }
  return "border-blue-300/70 bg-blue-100/70 text-blue-800";
}

function EyeIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-5 w-5"
      aria-hidden="true"
    >
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function ChartIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-5 w-5"
      aria-hidden="true"
    >
      <line x1="6" y1="20" x2="6" y2="12" />
      <line x1="12" y1="20" x2="12" y2="4" />
      <line x1="18" y1="20" x2="18" y2="8" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-5 w-5"
      aria-hidden="true"
    >
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
    </svg>
  );
}

const ICON_BUTTON =
  "inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-blue-200/60 bg-white/70 text-blue-700 hover:bg-blue-100 disabled:opacity-50";

function RoomCard({
  room,
  canRemove,
  removing,
  onRemove,
}: {
  room: RoomSummary;
  canRemove: boolean;
  removing: boolean;
  onRemove: (roomId: string) => void;
}) {
  const status = room.status ?? "draft";
  const label = roomStatusLabel(status);
  const active = isRoomActive(status);
  const [showStats, setShowStats] = useState(false);

  const stats = room.statistics;
  const statPlayers = stats?.players ?? [];

  return (
    <article
      className={`glass flex h-full flex-col gap-4 p-5 transition-transform duration-200 hover:-translate-y-0.5 ${
        active ? "ring-1 ring-emerald-300/60" : ""
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-lg font-semibold text-blue-900">{room.title}</h3>
          <p className="muted text-xs">Room {room.roomId}</p>
        </div>
        <span
          className={`shrink-0 rounded-full border px-2.5 py-1 text-xs font-semibold ${roomStatusTone(
            status,
          )}`}
        >
          {label}
        </span>
      </div>

      <dl className="grid grid-cols-2 gap-2 text-sm text-blue-900/80">
        <div>
          <dt className="muted text-xs">Players</dt>
          <dd className="font-medium text-blue-900">{room.playerCount ?? 0}</dd>
        </div>
        <div>
          <dt className="muted text-xs">Grid</dt>
          <dd className="font-medium text-blue-900">
            {room.width ?? "?"} × {room.height ?? "?"}
          </dd>
        </div>
        <div>
          <dt className="muted text-xs">Clues</dt>
          <dd className="font-medium text-blue-900">{room.clueCount ?? 0}</dd>
        </div>
        <div>
          <dt className="muted text-xs">Availability</dt>
          <dd className={`font-medium ${active ? "text-emerald-700" : "text-slate-500"}`}>
            {active ? "Active now" : "Not active"}
          </dd>
        </div>
      </dl>

      <div className="mt-auto flex items-center gap-2">
        <Link
          href={`/rooms/${room.roomId}/join`}
          className="btn-primary flex-1 text-sm"
        >
          Join room
        </Link>
        <Link
          href={`/rooms/${room.roomId}`}
          aria-label="View room"
          title="View room"
          className={ICON_BUTTON}
        >
          <EyeIcon />
        </Link>
        <button
          type="button"
          onClick={() => setShowStats(true)}
          aria-label="Statistics"
          title="Statistics"
          className={ICON_BUTTON}
        >
          <ChartIcon />
        </button>
        {canRemove ? (
          <button
            type="button"
            onClick={() => onRemove(room.roomId)}
            disabled={removing}
            aria-label="Remove room"
            title="Remove room"
            className={`${ICON_BUTTON} text-rose-700 hover:bg-rose-100`}
          >
            <TrashIcon />
          </button>
        ) : null}
      </div>

      {showStats ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={`Statistics for ${room.title}`}
          className="fixed inset-0 z-50 flex items-center justify-center bg-blue-950/60 p-4 backdrop-blur-sm"
          onClick={() => setShowStats(false)}
        >
          <div
            className="glass-strong flex max-h-[90vh] w-full max-w-md flex-col gap-3 p-5"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-lg font-semibold text-blue-900">
                {room.title} — Statistics
              </h3>
              <button
                type="button"
                onClick={() => setShowStats(false)}
                className="btn-ghost text-sm"
              >
                Close
              </button>
            </div>

            {statPlayers.length === 0 ? (
              <p className="muted text-sm">No players yet.</p>
            ) : (
              <ul className="flex flex-col gap-1.5" aria-label="Player statistics">
                {statPlayers.map((player) => (
                  <li
                    key={player.playerId}
                    className="flex items-center justify-between rounded-md border border-blue-200/50 bg-white/70 px-3 py-1.5 text-sm"
                  >
                    <span className="flex min-w-0 items-center gap-2">
                      <span
                        className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
                        style={{ backgroundColor: player.color }}
                      />
                      <span className="truncate font-medium text-blue-900">
                        {player.displayName}
                      </span>
                    </span>
                    <span className="font-semibold text-blue-900">
                      {player.solvedClues}
                    </span>
                  </li>
                ))}
              </ul>
            )}

            <div className="grid grid-cols-2 gap-2 border-t border-blue-200/50 pt-3">
              <div className="glass-soft flex flex-col items-center gap-0.5 rounded-md px-3 py-2">
                <span className="text-xs text-blue-800">Players total</span>
                <span
                  data-testid="stat-players-total"
                  className="text-xl font-bold text-blue-900"
                >
                  {stats?.playersTotal ?? 0}
                </span>
              </div>
              <div className="glass-soft flex flex-col items-center gap-0.5 rounded-md px-3 py-2">
                <span className="text-xs text-blue-800">Admin</span>
                <span
                  data-testid="stat-admin-total"
                  className="text-xl font-bold text-blue-900"
                >
                  {stats?.adminTotal ?? 0}
                </span>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </article>
  );
}

type PlayerTotal = {
  displayName: string;
  totalScore: number;
  color?: string | null;
};

export default function Page() {
  const [backendStatus, setBackendStatus] = useState<
    "checking" | "connected" | "offline"
  >("checking");
  const [rooms, setRooms] = useState<RoomSummary[]>([]);
  const [roomsLoading, setRoomsLoading] = useState(true);
  const [roomsError, setRoomsError] = useState<string | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [isGod, setIsGod] = useState(false);
  const [signedIn, setSignedIn] = useState(false);
  const [nickname, setNickname] = useState<string | null>(null);
  const [nicknameDraft, setNicknameDraft] = useState("");
  const [savingNickname, setSavingNickname] = useState(false);
  const [removingRoomId, setRemovingRoomId] = useState<string | null>(null);
  const [totals, setTotals] = useState<PlayerTotal[]>([]);
  const [totalsLoading, setTotalsLoading] = useState(true);

  const base = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

  useEffect(() => {
    let cancelled = false;
    fetch(`${base}/health`)
      .then(async (res) => {
        if (cancelled) return;
        if (!res.ok) {
          setBackendStatus("offline");
          return;
        }
        const body = await res.json();
        if (!cancelled) {
          setBackendStatus(body?.status === "ok" ? "connected" : "offline");
        }
      })
      .catch(() => {
        if (!cancelled) setBackendStatus("offline");
      });
    return () => {
      cancelled = true;
    };
  }, [base]);

  useEffect(() => {
    const unsubscribe = onAuthChange(async (user) => {
      setSignedIn(Boolean(user));
      if (!user) {
        setIsGod(false);
        setIsAdmin(false);
        setNickname(null);
        return;
      }
      try {
        const token = await getIdToken();
        if (token) {
          const godRes = await fetch(`${base}/god/me`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          setIsGod(godRes.ok);
        }
        const adminRes = await adminFetch("/admin/me");
        setIsAdmin(adminRes.ok);
        const profile = await getProfile();
        setNickname(profile.nickname);
      } catch {
        setIsGod(false);
        setIsAdmin(false);
        setNickname(null);
      }
    });
    return unsubscribe;
  }, [base]);

  useEffect(() => {
    let cancelled = false;
    const loadTotals = () => {
      fetch(`${base}/players/totals`, { credentials: "include" })
        .then(async (res) => {
          if (!res.ok) return;
          const body = await res.json();
          if (!cancelled) setTotals(body?.players ?? []);
        })
        .catch(() => {})
        .finally(() => {
          if (!cancelled) setTotalsLoading(false);
        });
    };
    loadTotals();
    const timer = window.setInterval(loadTotals, 15000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [base]);

  const handleRemoveRoom = async (targetRoomId: string) => {
    const confirmed = window.confirm(`Remove room ${targetRoomId}?`);
    if (!confirmed) return;
    setRemovingRoomId(targetRoomId);
    try {
      await adminFetch(`/admin/rooms/${targetRoomId}`, {
        method: "DELETE",
      });
    } catch {
      // ignore; the gallery refreshes via Firestore once the room is gone
    } finally {
      setRemovingRoomId(null);
    }
  };

  useEffect(() => {
    const unsubscribe = subscribeRooms(
      (next) => {
        const newestFirst = [...next].sort(
          (a, b) =>
            (b.createdAt ?? b.updatedAt ?? 0) - (a.createdAt ?? a.updatedAt ?? 0),
        );
        setRooms(newestFirst);
        setRoomsLoading(false);
        setRoomsError(null);
      },
      () => {
        setRoomsLoading(false);
        setRoomsError("Failed to load rooms from Firestore.");
      },
    );
    return unsubscribe;
  }, []);

  const saveNickname = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const value = nicknameDraft.trim();
    if (value.length < 2) return;
    setSavingNickname(true);
    try {
      const profile = await saveProfile(value);
      setNickname(profile.nickname);
      setNicknameDraft("");
    } catch {
      // keep the prompt; the user can retry
    } finally {
      setSavingNickname(false);
    }
  };

  const activeRooms = rooms.filter((room) => isRoomActive(room.status)).length;
  const backendLabel =
    backendStatus === "checking"
      ? "Checking backend..."
      : backendStatus === "connected"
        ? "Backend connected"
        : "Offline";

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-8 p-6">
      <header className="glass flex flex-wrap items-center justify-between gap-4 px-6 py-5">
        <div className="flex flex-col gap-1">
          <h1 className="brand text-4xl">Crossword Arena</h1>
          <p className="muted text-sm">
            Competitive crossword, solved together in real time.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium ${backendTone(
              backendStatus,
            )}`}
          >
            <span
              className={`inline-block h-2 w-2 rounded-full ${
                backendStatus === "connected"
                  ? "bg-emerald-500"
                  : backendStatus === "offline"
                    ? "bg-rose-500"
                    : "bg-blue-500"
              }`}
            />
            {backendLabel}
          </span>
          <Link href="/admin/rooms" className="btn-ghost text-sm">
            Admin
          </Link>
          {isGod ? (
            <Link href="/god" className="btn-ghost text-sm">
              GOD
            </Link>
          ) : null}
          {signedIn ? (
            <button
              type="button"
              onClick={() => void signOutGoogle()}
              className="btn-ghost text-sm"
            >
              {nickname ? `Sign out (${nickname})` : "Sign out"}
            </button>
          ) : (
            <button
              type="button"
              onClick={() => void signInWithGoogle()}
              className="btn-ghost text-sm"
            >
              Sign in
            </button>
          )}
        </div>
      </header>

      {signedIn && nickname === null ? (
        <section className="glass flex flex-wrap items-center gap-3 px-6 py-4">
          <div className="flex flex-col gap-1">
            <h2 className="text-lg font-semibold text-blue-900">Choose a nickname</h2>
            <p className="muted text-xs">
              This is the name shown to other players.
            </p>
          </div>
          <form onSubmit={saveNickname} className="flex flex-1 flex-col gap-2 sm:flex-row">
            <input
              type="text"
              value={nicknameDraft}
              onChange={(e) => setNicknameDraft(e.target.value)}
              className="input flex-1"
              placeholder="Your nickname"
              maxLength={20}
            />
            <button
              type="submit"
              disabled={savingNickname || nicknameDraft.trim().length < 2}
              className="btn-primary text-sm"
            >
              {savingNickname ? "Saving..." : "Save nickname"}
            </button>
          </form>
        </section>
      ) : null}

      <section className="glass px-6 py-8">
        <div className="glass-soft mx-auto flex max-w-xl flex-col justify-center gap-2 p-5">
          <p className="text-sm font-medium text-blue-800">Rooms right now</p>
          <p className="text-4xl font-bold text-blue-900">{activeRooms}</p>
          <p className="muted text-sm">
            active · {rooms.length} total
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            <span className="rounded-full border border-blue-300/60 bg-white/60 px-2.5 py-1 text-xs font-medium text-blue-800">
              {rooms.reduce((total, room) => total + (room.playerCount ?? 0), 0)} players
            </span>
            <span className="rounded-full border border-blue-300/60 bg-white/60 px-2.5 py-1 text-xs font-medium text-blue-800">
              {rooms.length} rooms
            </span>
          </div>
        </div>
      </section>

      <section className="glass flex flex-col gap-3 px-6 py-5">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <div>
            <h2 className="text-xl font-semibold text-blue-900">Lifetime scores</h2>
            <p className="muted text-sm">
              Total points from every room. Scores stay after a room ends.
            </p>
          </div>
          {totalsLoading ? <span className="muted text-xs">Loading…</span> : null}
        </div>
        {totals.length === 0 ? (
          <p className="muted text-sm">No scored answers yet.</p>
        ) : (
          <ol className="grid gap-1.5 sm:grid-cols-3 lg:grid-cols-4">
            {totals.map((player) => (
              <li
                key={player.displayName}
                className="flex items-center justify-between gap-2 rounded-md border border-blue-200/50 bg-white/60 px-2 py-1 text-xs"
              >
                <span className="flex min-w-0 items-center gap-1.5">
                  <span
                    className="inline-block h-2 w-2 shrink-0 rounded-full"
                    style={{ backgroundColor: player.color ?? "#94A3B8" }}
                  />
                  <span className="truncate font-medium text-blue-900">
                    {player.displayName}
                  </span>
                </span>
                <span className="font-semibold text-blue-900">
                  {player.totalScore}
                </span>
              </li>
            ))}
          </ol>
        )}
      </section>

      <section className="flex flex-col gap-4">
        <div>
          <h2 className="text-2xl font-semibold text-blue-900">Room gallery</h2>
          <p className="muted text-sm">
            Every room on this server, updating live.
          </p>
        </div>

        {roomsLoading ? (
          <LoadingSpinner label="Loading rooms..." />
        ) : roomsError ? (
          <ErrorMessage
            title="Could not load rooms"
            message={roomsError}
          />
        ) : rooms.length === 0 ? (
          <EmptyState
            title="No rooms yet"
            message="Rooms will appear here as soon as they are created."
          />
        ) : (
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {rooms.map((room) => (
              <RoomCard
                key={room.roomId}
                room={room}
                canRemove={isAdmin}
                removing={removingRoomId === room.roomId}
                onRemove={handleRemoveRoom}
              />
            ))}
          </div>
        )}
      </section>
    </main>
  );
}

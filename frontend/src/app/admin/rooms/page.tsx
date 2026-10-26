"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import EmptyState from "@/components/ui/EmptyState";
import ErrorMessage from "@/components/ui/ErrorMessage";
import LoadingSpinner from "@/components/ui/LoadingSpinner";
import {
  RoomSummary,
  isRoomActive,
  roomStatusLabel,
  roomStatusTone,
} from "@/utils/rooms";

function AdminRoomCard({ room }: { room: RoomSummary }) {
  const status = room.status ?? "draft";
  const active = isRoomActive(status);

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
          {roomStatusLabel(status)}
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

      <div className="mt-auto flex flex-col gap-2">
        <Link
          href={`/admin/rooms/${room.roomId}`}
          className="btn-primary w-full text-sm"
        >
          Open dashboard
        </Link>
        <div className="flex gap-2">
          <Link href={`/rooms/${room.roomId}`} className="btn-ghost flex-1 text-sm">
            Player view
          </Link>
          <Link
            href={`/rooms/${room.roomId}/join`}
            className="btn-ghost flex-1 text-sm"
          >
            Join as player
          </Link>
        </div>
      </div>
    </article>
  );
}

export default function AdminRoomsPage() {
  const router = useRouter();
  const [rooms, setRooms] = useState<RoomSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [unauthorized, setUnauthorized] = useState(false);
  const [password, setPassword] = useState("");
  const [signingIn, setSigningIn] = useState(false);
  const [signInError, setSignInError] = useState<string | null>(null);
  const [roomTitle, setRoomTitle] = useState("");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const base = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

  const loadRooms = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${base}/admin/rooms`, { credentials: "include" });
      if (res.status === 401 || res.status === 403) {
        setUnauthorized(true);
        setRooms([]);
        return;
      }
      if (!res.ok) {
        setError(`Failed to load rooms (status ${res.status})`);
        return;
      }
      const body = await res.json();
      setRooms(Array.isArray(body) ? (body as RoomSummary[]) : []);
      setUnauthorized(false);
    } catch {
      setError("Network error while loading rooms.");
    } finally {
      setLoading(false);
    }
  }, [base]);

  useEffect(() => {
    void loadRooms();
  }, [loadRooms]);

  const signIn = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const trimmed = password.trim();
    if (!trimmed) {
      setSignInError("Enter the admin password to continue.");
      return;
    }
    setSigningIn(true);
    setSignInError(null);
    try {
      const res = await fetch(`${base}/admin/session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ password: trimmed }),
      });
      if (!res.ok) {
        setSignInError("Incorrect admin password.");
        return;
      }
      setPassword("");
      setUnauthorized(false);
      await loadRooms();
    } catch {
      setSignInError("Network error. Please try again.");
    } finally {
      setSigningIn(false);
    }
  };

  const createRoom = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!imageFile) {
      setCreateError("Choose a crossword image.");
      return;
    }
    setCreating(true);
    setCreateError(null);
    try {
      const bytes = await imageFile.arrayBuffer();
      const title = roomTitle.trim() || "New Room";
      const res = await fetch(
        `${base}/admin/rooms?title=${encodeURIComponent(title)}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/octet-stream" },
          credentials: "include",
          body: bytes,
        },
      );
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as {
          detail?: string;
        };
        setCreateError(
          typeof body.detail === "string"
            ? body.detail
            : `Failed to create room (status ${res.status})`,
        );
        return;
      }
      const body = (await res.json()) as { roomId?: string };
      if (body.roomId) {
        router.push(`/admin/rooms/${body.roomId}`);
      }
    } catch {
      setCreateError("Network error. Please try again.");
    } finally {
      setCreating(false);
    }
  };

  const totalPlayers = rooms.reduce(
    (total, room) => total + (room.playerCount ?? 0),
    0,
  );

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-8 p-6">
      <header className="glass flex flex-wrap items-center justify-between gap-4 px-6 py-5">
        <div className="flex flex-col gap-1">
          <h1 className="brand text-3xl">Admin rooms</h1>
          <p className="muted text-sm">
            Manage every room, open a dashboard, or jump into the puzzle editor.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link href="/admin/puzzles/editor" className="btn-ghost text-sm">
            Puzzle editor
          </Link>
          <Link href="/" className="btn-ghost text-sm">
            Back to site
          </Link>
        </div>
      </header>

      {unauthorized ? (
        <section className="glass flex flex-col gap-4 px-6 py-8">
          <div className="flex flex-col gap-2">
            <h2 className="text-2xl font-semibold text-blue-900">Admin entry</h2>
            <p className="muted text-sm">
              Enter the admin password to open the room dashboard.
            </p>
          </div>
          <form onSubmit={signIn} className="flex flex-col gap-3 sm:max-w-xl sm:flex-row">
            <label className="flex flex-1 flex-col gap-1 text-start">
              <span className="text-sm font-medium">Admin password</span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input"
                placeholder="Enter admin password"
                autoComplete="current-password"
              />
            </label>
            <button
              type="submit"
              disabled={signingIn}
              className="btn-primary sm:self-end"
            >
              {signingIn ? "Signing in..." : "Enter admin area"}
            </button>
          </form>
          {signInError ? (
            <p role="alert" className="text-sm font-medium text-rose-700">
              {signInError}
            </p>
          ) : null}
          <p className="muted text-xs">
            Local development password: <strong>1234</strong>
          </p>
        </section>
      ) : loading ? (
        <LoadingSpinner label="Loading admin rooms..." />
      ) : error ? (
        <ErrorMessage
          title="Could not load admin rooms"
          message={error}
          onRetry={() => void loadRooms()}
        />
      ) : (
        <>
          <section className="glass flex flex-col gap-3 px-6 py-4">
            <div>
              <h2 className="text-lg font-semibold text-blue-900">Create room</h2>
              <p className="muted text-xs">
                Upload a crossword image. The backend parses the grid and extracts
                the clues with Google Gemini.
              </p>
            </div>
            <form
              onSubmit={createRoom}
              className="flex flex-col gap-3 sm:flex-row sm:items-end"
            >
              <label className="flex flex-1 flex-col gap-1 text-start">
                <span className="text-sm font-medium">Room title</span>
                <input
                  type="text"
                  value={roomTitle}
                  onChange={(e) => setRoomTitle(e.target.value)}
                  className="input"
                  placeholder="Room title"
                />
              </label>
              <label className="flex flex-1 flex-col gap-1 text-start">
                <span className="text-sm font-medium">Crossword image</span>
                <input
                  type="file"
                  accept="image/*"
                  onChange={(e) => setImageFile(e.target.files?.[0] ?? null)}
                  className="input"
                />
              </label>
              <button
                type="submit"
                disabled={creating || !imageFile}
                className="btn-primary sm:self-end"
              >
                {creating ? "Creating..." : "Create room"}
              </button>
            </form>
            {createError ? (
              <p role="alert" className="text-sm font-medium text-rose-700">
                {createError}
              </p>
            ) : null}
          </section>

          <section className="glass flex flex-wrap items-center justify-between gap-4 px-6 py-5">
            <div className="flex flex-wrap gap-6">
              <div>
                <p className="muted text-xs">Rooms</p>
                <p className="text-2xl font-bold text-blue-900">{rooms.length}</p>
              </div>
              <div>
                <p className="muted text-xs">Active</p>
                <p className="text-2xl font-bold text-emerald-700">
                  {rooms.filter((room) => isRoomActive(room.status)).length}
                </p>
              </div>
              <div>
                <p className="muted text-xs">Players</p>
                <p className="text-2xl font-bold text-blue-900">{totalPlayers}</p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => void loadRooms()}
              disabled={loading}
              className="btn-ghost text-sm"
            >
              Refresh
            </button>
          </section>

          {rooms.length === 0 ? (
            <EmptyState
              title="No rooms yet"
              message="Seed a room to see it appear in the admin gallery."
            />
          ) : (
            <section className="flex flex-col gap-4">
              <h2 className="text-xl font-semibold text-blue-900">All rooms</h2>
              <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                {rooms.map((room) => (
                  <AdminRoomCard key={room.roomId} room={room} />
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </main>
  );
}

"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { onAuthChange, getIdToken, getProfile, saveProfile, signInWithGoogle } from "@/lib/auth";

export default function JoinPage() {
  const router = useRouter();
  const params = useParams<{ roomId: string }>();
  const roomId = params.roomId;

  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [signedIn, setSignedIn] = useState(false);
  const [nickname, setNickname] = useState<string | null>(null);
  const [nicknameDraft, setNicknameDraft] = useState("");
  const [authBusy, setAuthBusy] = useState(false);

  const base = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

  useEffect(() => {
    const unsubscribe = onAuthChange(async (user) => {
      setSignedIn(Boolean(user));
      if (user) {
        try {
          const profile = await getProfile();
          setNickname(profile.nickname);
        } catch {
          setNickname(null);
        }
      } else {
        setNickname(null);
      }
    });
    return unsubscribe;
  }, []);

  const joinWithAuthorization = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const token = await getIdToken();
      const res = await fetch(`${base}/rooms/${roomId}/join`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token ?? ""}`,
        },
        credentials: "include",
        body: JSON.stringify({ displayName: nickname ?? "player" }),
      });
      if (res.ok) {
        router.push(`/rooms/${roomId}`);
        return;
      }
      let message = `Request failed with status ${res.status}`;
      try {
        const body = await res.json();
        if (body && typeof body.detail === "string") {
          message = body.detail;
        }
      } catch {
        // keep default message
      }
      setError(message);
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleAnonymousJoin = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    if (displayName.trim().length === 0) {
      setError("Display name is required");
      return;
    }
    setSubmitting(true);
    try {
      const res = await fetch(`${base}/rooms/${roomId}/join`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ displayName }),
      });
      if (res.ok) {
        router.push(`/rooms/${roomId}`);
        return;
      }
      let message = `Request failed with status ${res.status}`;
      try {
        const body = await res.json();
        if (body && typeof body.detail === "string") {
          message = body.detail;
        }
      } catch {
        // keep default message
      }
      setError(message);
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  const saveNickname = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    setAuthBusy(true);
    try {
      const profile = await saveProfile(nicknameDraft.trim());
      setNickname(profile.nickname);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save nickname");
    } finally {
      setAuthBusy(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <div className="glass-strong flex w-full max-w-sm flex-col gap-4 px-8 py-10">
        <div className="flex items-center justify-between">
          <h1 className="brand text-2xl">Join Room</h1>
          <Link href="/" className="btn-ghost shrink-0 text-sm">
            Home
          </Link>
        </div>

        {!signedIn ? (
          <>
            <button
              type="button"
              onClick={() => void signInWithGoogle()}
              className="btn-primary w-full"
            >
              Sign in with Google
            </button>
            <p className="muted text-center text-xs">or join without an account</p>
          </>
        ) : nickname === null ? (
          <form onSubmit={saveNickname} className="flex flex-col gap-3">
            <label className="flex flex-col gap-1 text-start">
              <span className="text-sm font-medium">Nickname</span>
              <input
                type="text"
                value={nicknameDraft}
                onChange={(e) => setNicknameDraft(e.target.value)}
                className="input"
                placeholder="Your nickname"
                maxLength={20}
              />
            </label>
            <button type="submit" disabled={authBusy} className="btn-primary w-full">
              {authBusy ? "Saving..." : "Save nickname"}
            </button>
          </form>
        ) : (
          <button
            type="button"
            onClick={() => void joinWithAuthorization()}
            disabled={submitting}
            className="btn-primary w-full"
          >
            {submitting ? "Joining..." : `Join as ${nickname}`}
          </button>
        )}

        {!signedIn ? (
          <form onSubmit={handleAnonymousJoin} className="flex flex-col gap-4">
            <label className="flex flex-col gap-1 text-start">
              <span className="text-sm font-medium">Display Name</span>
              <input
                type="text"
                name="displayName"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                className="input"
                placeholder="Your name"
              />
            </label>
            <p className="muted text-sm">
              Your crossword color is assigned automatically when you join.
            </p>
            <button type="submit" disabled={submitting} className="btn-primary w-full">
              {submitting ? "Joining..." : "Join"}
            </button>
          </form>
        ) : null}

        {error ? (
          <p role="alert" className="text-sm font-medium text-blue-700">
            {error}
          </p>
        ) : null}
      </div>
    </main>
  );
}

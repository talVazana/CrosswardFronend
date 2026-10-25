"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

export default function JoinPage() {
  const router = useRouter();
  const params = useParams<{ roomId: string }>();
  const roomId = params.roomId;

  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);

    if (displayName.trim().length === 0) {
      setError("Display name is required");
      return;
    }

    setSubmitting(true);
    try {
      const base = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
      const res = await fetch(`${base}/rooms/${roomId}/join`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ displayName }),
      });

      if (res.status >= 200 && res.status < 300) {
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

  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <form
        onSubmit={handleSubmit}
        className="glass-strong flex w-full max-w-sm flex-col gap-4 px-8 py-10"
      >
        <div className="flex items-center justify-between">
          <h1 className="brand text-2xl">Join Room</h1>
          <Link href="/" className="btn-ghost shrink-0 text-sm">
            Home
          </Link>
        </div>

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

        {error ? (
          <p role="alert" className="text-sm font-medium text-blue-700">
            {error}
          </p>
        ) : null}

        <button type="submit" disabled={submitting} className="btn-primary w-full">
          {submitting ? "Joining..." : "Join"}
        </button>
      </form>
    </main>
  );
}

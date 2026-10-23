"use client";

import { useEffect, useState } from "react";

export interface ScoreEntry {
  playerId?: string;
  id?: string;
  displayName: string;
  color: string;
  totalPoints: number;
}

interface ScoreboardProps {
  roomId: string;
}

export default function Scoreboard({ roomId }: ScoreboardProps) {
  const [scores, setScores] = useState<ScoreEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const base = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
        const res = await fetch(`${base}/rooms/${roomId}/scores`, {
          credentials: "include",
        });
        if (cancelled) return;
        if (!res.ok) {
          setError(`Failed to load scores (status ${res.status})`);
          return;
        }
        const body = (await res.json()) as ScoreEntry[];
        if (cancelled) return;
        setScores(Array.isArray(body) ? body : []);
      } catch {
        if (!cancelled) {
          setError("Network error. Please try again.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [roomId]);

  if (loading) {
    return (
      <p role="status" className="text-gray-600">
        Loading...
      </p>
    );
  }

  if (error) {
    return (
      <p role="alert" className="text-sm text-red-600">
        {error}
      </p>
    );
  }

  if (scores.length === 0) {
    return <p className="text-sm text-gray-500">No scores yet.</p>;
  }

  return (
    <ul className="flex flex-col gap-2" aria-label="Scoreboard">
      {scores.map((entry) => {
        const key = entry.playerId ?? entry.id ?? entry.displayName;
        return (
          <li
            key={key}
            className="flex items-center gap-3 rounded border border-gray-200 px-3 py-2"
          >
            <span
              data-testid="score-color"
              className="inline-block h-4 w-4 rounded-full border border-gray-300"
              style={{ backgroundColor: entry.color }}
            />
            <span className="text-sm font-medium">{entry.displayName}</span>
            <span data-testid="score-value" className="ml-auto text-sm font-semibold">
              {entry.totalPoints}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

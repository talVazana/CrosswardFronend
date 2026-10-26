"use client";

export interface ScoreEntry {
  playerId?: string;
  id?: string;
  displayName: string;
  color: string;
  totalPoints: number;
}

interface ScoreboardProps {
  scores?: ScoreEntry[];
  loading?: boolean;
}

export default function Scoreboard({
  scores,
  loading = false,
}: ScoreboardProps) {
  if (loading) {
    return (
      <p role="status" className="muted">
        Loading...
      </p>
    );
  }

  if (!scores || scores.length === 0) {
    return <p className="muted text-sm">No scores yet.</p>;
  }

  return (
    <ul className="flex flex-col gap-2" aria-label="Scoreboard">
      {scores.map((entry) => {
        const key = entry.playerId ?? entry.id ?? entry.displayName;
        return (
          <li
            key={key}
            className="glass-soft flex items-center gap-3 px-3 py-2"
          >
            <span
              data-testid="score-color"
              className="inline-block h-4 w-4 rounded-full border border-blue-900/20 opacity-70"
              style={{ backgroundColor: entry.color }}
            />
            <span className="text-sm font-medium text-blue-900">
              {entry.displayName}
            </span>
            <span
              data-testid="score-value"
              className="ml-auto text-sm font-semibold text-blue-700"
            >
              {entry.totalPoints}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

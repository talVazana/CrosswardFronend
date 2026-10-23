"use client";

import { KeyboardEvent, useCallback, useEffect, useRef, useState } from "react";
import { useCrosswordSelection } from "@/hooks/useCrosswordSelection";
import { build2DGrid, Cell } from "@/utils/grid";

export interface Clue {
  clueId: string;
  number: number;
  direction: "across" | "down";
  text: string;
  answerLength: number;
}

export interface Puzzle {
  puzzleId: string;
  title: string;
  width: number;
  height: number;
  cells: Cell[];
  clues: Clue[];
}

type FeedbackState = "correct" | "incorrect" | "pending" | null;

interface CrosswordGridProps {
  roomId: string;
  puzzle: Puzzle;
}

function cellsForClue(grid: Cell[][], clue: Clue): Cell[] {
  const cells: Cell[] = [];
  for (const row of grid) {
    for (const cell of row) {
      if (cell.type === "black") continue;
      const startsHere =
        cell.number === clue.number &&
        (clue.direction === "across" ? cell.startsAcross : cell.startsDown);
      if (!startsHere) continue;
      let r = cell.row;
      let c = cell.col;
      for (let i = 0; i < clue.answerLength; i++) {
        const next = grid[r]?.[c];
        if (!next || next.type === "black") break;
        cells.push(next);
        if (clue.direction === "across") c += 1;
        else r += 1;
      }
      return cells;
    }
  }
  return cells;
}

export default function CrosswordGrid({ roomId, puzzle }: CrosswordGridProps) {
  const grid = build2DGrid(puzzle.cells, puzzle.width, puzzle.height);
  const { selectedCell, currentDirection, handleCellClick } = useCrosswordSelection();

  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [revealed, setRevealed] = useState<Record<string, boolean>>({});
  const [feedback, setFeedback] = useState<FeedbackState>(null);
  const [submitting, setSubmitting] = useState(false);
  const [revealing, setRevealing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const shakeTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clueForCell = (row: number, col: number, direction: "across" | "down") =>
    puzzle.clues.find((clue) => {
      if (clue.direction !== direction) return false;
      return cellsForClue(grid, clue).some((c) => c.row === row && c.col === col);
    });

  const activeClue =
    selectedCell != null
      ? clueForCell(selectedCell.row, selectedCell.col, currentDirection) ??
        clueForCell(selectedCell.row, selectedCell.col, currentDirection === "across" ? "down" : "across") ??
        null
      : null;

  const activeClueId = activeClue?.clueId ?? null;
  const isRevealed = activeClueId ? revealed[activeClueId] ?? false : false;
  const draft = activeClueId ? drafts[activeClueId] ?? "" : "";
  const activeCells = activeClue ? cellsForClue(grid, activeClue) : [];
  const activeCellKeys = new Set(activeCells.map((c) => `${c.row}-${c.col}`));
  const draftByCell = new Map<string, string>();
  activeCells.forEach((cell, i) => {
    draftByCell.set(`${cell.row}-${cell.col}`, draft[i] ?? "");
  });

  useEffect(() => {
    setFeedback(null);
    setError(null);
  }, [activeClueId]);

  useEffect(() => {
    return () => {
      if (shakeTimeout.current) clearTimeout(shakeTimeout.current);
    };
  }, []);

  const submit = useCallback(async () => {
    if (!activeClueId || submitting || isRevealed) return;
    if (draft.trim().length === 0) return;

    setSubmitting(true);
    setError(null);
    try {
      const base = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
      const res = await fetch(
        `${base}/rooms/${roomId}/clues/${activeClueId}/submissions`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ answer: draft }),
        },
      );
      if (!res.ok) {
        setError(`Submission failed (status ${res.status})`);
        return;
      }
      const body = (await res.json()) as { status?: string };
      if (
        body.status === "correct" ||
        body.status === "incorrect" ||
        body.status === "pending"
      ) {
        setFeedback(body.status);
      } else {
        setError("Unexpected response from server");
      }
      if (body.status === "incorrect") {
        if (shakeTimeout.current) clearTimeout(shakeTimeout.current);
        shakeTimeout.current = setTimeout(() => setFeedback(null), 600);
      }
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }, [activeClueId, draft, roomId, submitting, isRevealed]);

  const reveal = useCallback(async () => {
    if (!activeClueId || revealing || isRevealed) return;
    const confirmed = window.confirm(
      "Are you sure? You will not earn points for this clue.",
    );
    if (!confirmed) return;

    setRevealing(true);
    setError(null);
    try {
      const base = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
      const res = await fetch(
        `${base}/rooms/${roomId}/clues/${activeClueId}/reveal`,
        {
          method: "POST",
          credentials: "include",
        },
      );
      if (res.status === 400) {
        setError("Answer not available yet");
        return;
      }
      if (!res.ok) {
        setError(`Reveal failed (status ${res.status})`);
        return;
      }
      const body = (await res.json()) as { answer?: string };
      if (typeof body.answer !== "string") {
        setError("Unexpected response from server");
        return;
      }
      setDrafts((prev) => ({ ...prev, [activeClueId]: body.answer as string }));
      setRevealed((prev) => ({ ...prev, [activeClueId]: true }));
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setRevealing(false);
    }
  }, [activeClueId, revealing, isRevealed, roomId]);

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (isRevealed) return;
    if (e.key === "Enter") {
      e.preventDefault();
      void submit();
    }
  };

  const cellClass = (cell: Cell): string => {
    const base =
      "relative flex h-9 w-9 items-center justify-center border border-gray-400 text-sm font-semibold";
    if (cell.type === "black") return `${base} bg-gray-900`;
    const isSelected =
      selectedCell != null && selectedCell.row === cell.row && selectedCell.col === cell.col;
    const isActive = activeCellKeys.has(`${cell.row}-${cell.col}`);
    let classes = `${base} bg-white text-gray-900`;
    if (isSelected) classes += " bg-blue-200";
    else if (isActive) classes += " bg-blue-50";
    if (feedback === "correct" && isActive) classes += " bg-green-400";
    if (feedback === "incorrect" && isActive) classes += " bg-red-400 animate-[shake_0.5s_ease-in-out]";
    if (feedback === "pending" && isActive) classes += " bg-yellow-200";
    const clueIdForCell = clueForCell(cell.row, cell.col, "across")?.clueId ??
      clueForCell(cell.row, cell.col, "down")?.clueId;
    if (clueIdForCell && revealed[clueIdForCell] && isActive) {
      classes += " text-amber-700";
    }
    return classes;
  };

  return (
    <div
      className="flex flex-col gap-4"
      tabIndex={0}
      onKeyDown={handleKeyDown}
      role="application"
      aria-label="Crossword grid"
    >
      <div
        className="grid w-fit gap-0"
        style={{ gridTemplateColumns: `repeat(${puzzle.width}, minmax(0, 1fr))` }}
      >
        {grid.map((row) =>
          row.map((cell) => (
            <button
              key={`${cell.row}-${cell.col}`}
              type="button"
              data-testid={`cell-${cell.row}-${cell.col}`}
              className={cellClass(cell)}
              onClick={() => handleCellClick(cell.row, cell.col, cell)}
              disabled={cell.type === "black"}
            >
              {cell.number != null ? (
                <span className="absolute left-0.5 top-0 text-[8px] text-gray-500">
                  {cell.number}
                </span>
              ) : null}
              {draftByCell.get(`${cell.row}-${cell.col}`) ?? ""}
            </button>
          )),
        )}
      </div>

      <section className="flex flex-col gap-2 rounded-lg border border-gray-200 p-4">
        {activeClue ? (
          <>
            <h2 className="text-lg font-medium">
              {activeClue.number} {activeClue.direction === "across" ? "Across" : "Down"}
            </h2>
            <p className="text-sm text-gray-700">{activeClue.text}</p>
            <input
              type="text"
              aria-label="Answer draft"
              value={draft}
              onChange={(e) => {
                if (!activeClueId || isRevealed) return;
                setDrafts((prev) => ({ ...prev, [activeClueId]: e.target.value }));
                setFeedback(null);
              }}
              disabled={isRevealed}
              className="rounded border border-gray-300 px-3 py-2 disabled:bg-gray-100"
              placeholder={`Your answer (${activeClue.answerLength} letters)`}
            />
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => void submit()}
                disabled={isRevealed || draft.trim().length === 0 || submitting}
                className="rounded bg-blue-600 px-4 py-2 text-white disabled:opacity-50"
              >
                {submitting ? "Submitting..." : "Submit"}
              </button>
              <button
                type="button"
                onClick={() => void reveal()}
                disabled={isRevealed || revealing}
                className="rounded bg-amber-600 px-4 py-2 text-white disabled:opacity-50"
              >
                {revealing ? "Revealing..." : "Reveal Answer"}
              </button>
              {isRevealed ? (
                <span role="status" className="text-sm font-medium text-amber-700">
                  🔒 Revealed — no points for this clue
                </span>
              ) : null}
              {feedback === "correct" ? (
                <span role="status" className="text-sm font-medium text-green-700">
                  Correct!
                </span>
              ) : null}
              {feedback === "incorrect" ? (
                <span role="status" className="text-sm font-medium text-red-700">
                  Incorrect, try again
                </span>
              ) : null}
              {feedback === "pending" ? (
                <span role="status" className="text-sm font-medium text-yellow-700">
                  Waiting for Admin
                </span>
              ) : null}
            </div>
            {error ? (
              <p role="alert" className="text-sm text-red-600">
                {error}
              </p>
            ) : null}
          </>
        ) : (
          <p className="text-sm text-gray-500">Select a cell to see a clue.</p>
        )}
      </section>
    </div>
  );
}

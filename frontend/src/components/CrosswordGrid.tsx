"use client";

import {
  CSSProperties,
  KeyboardEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useCrosswordSelection, type Direction } from "@/hooks/useCrosswordSelection";
import { build2DGrid, Cell } from "@/utils/grid";
import { cellKey, cellsForClue, softColor } from "@/utils/crossword";
import { roomFetch } from "@/lib/roomSession";

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
  displayClues?: Clue[];
}

type FeedbackState = "correct" | "incorrect" | "pending" | null;

export interface ClueSolvedEvent {
  type: "CLUE_SOLVED";
  clueId: string;
  firstSolverColor: string;
  points: number;
}

export interface RoomStatusChangedEvent {
  type: "ROOM_STATUS_CHANGED";
  status: string;
}

export type LiveRoomEvent = ClueSolvedEvent | RoomStatusChangedEvent;

const EMPTY_SOLVED_CLUES: Record<string, string> = {};

function rejectionSeenKey(roomId: string): string {
  return `crossword-rejection-seen:${roomId}`;
}

function loadSeenRejections(roomId: string): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(rejectionSeenKey(roomId));
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed)
      ? parsed.filter((value): value is string => typeof value === "string")
      : [];
  } catch {
    return [];
  }
}

interface CrosswordGridProps {
  roomId: string;
  puzzle: Puzzle;
  roomStatus?: string;
  liveEvent?: LiveRoomEvent | null;
  initialSolvedClues?: Record<string, string>;
  initialAnswers?: Record<string, string>;
  playerSolvedClues?: string[];
  playerRejected?: { clueId: string; submissionId: string }[];
  onClueSolved?: (clueId: string) => void;
  onClueRevealed?: (clueId: string) => void;
}

export default function CrosswordGrid({
  roomId,
  puzzle,
  roomStatus,
  liveEvent,
  initialSolvedClues = EMPTY_SOLVED_CLUES,
  initialAnswers,
  playerSolvedClues,
  playerRejected,
  onClueSolved,
  onClueRevealed,
}: CrosswordGridProps) {
  const grid = useMemo(
    () => build2DGrid(puzzle.cells, puzzle.width, puzzle.height),
    [puzzle.cells, puzzle.width, puzzle.height],
  );
  const { selectedCell, currentDirection, handleCellClick, setDirection } = useCrosswordSelection();

  const [letters, setLetters] = useState<Record<string, string>>({});
  const [revealedClues, setRevealedClues] = useState<Record<string, boolean>>({});
  const [solvedClues, setSolvedClues] = useState<Record<string, string>>(initialSolvedClues);
  const [feedback, setFeedback] = useState<FeedbackState>(null);
  const [lastPoints, setLastPoints] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [revealing, setRevealing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nextWriteIndex, setNextWriteIndex] = useState(0);
  const shakeTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastProcessedEventRef = useRef<LiveRoomEvent | null>(null);

  const isPaused = roomStatus === "paused";

  const clueThrough = useCallback(
    (row: number, col: number, direction: Direction): Clue | undefined =>
      puzzle.clues.find(
        (clue) =>
          clue.direction === direction &&
          cellsForClue(grid, clue).some((cell) => cell.row === row && cell.col === col),
      ),
    [grid, puzzle.clues],
  );

  const effectiveDirection: Direction = selectedCell
    ? clueThrough(selectedCell.row, selectedCell.col, currentDirection)
      ? currentDirection
      : clueThrough(
            selectedCell.row,
            selectedCell.col,
            currentDirection === "across" ? "down" : "across",
          )
        ? currentDirection === "across"
          ? "down"
          : "across"
        : currentDirection
    : currentDirection;

  const activeClue = selectedCell
    ? clueThrough(selectedCell.row, selectedCell.col, effectiveDirection) ?? null
    : null;
  const activeClueId = activeClue?.clueId ?? null;
  const activeCells = activeClue ? cellsForClue(grid, activeClue) : [];
  const activeCellKeys = new Set(activeCells.map((cell) => cellKey(cell.row, cell.col)));
  const selectedIndex = selectedCell
    ? activeCells.findIndex(
        (cell) => cell.row === selectedCell.row && cell.col === selectedCell.col,
      )
    : -1;

  const isRevealed = activeClueId ? revealedClues[activeClueId] ?? false : false;
  const ownSolvedClueIds = new Set(playerSolvedClues ?? []);
  const isOwnSolved = activeClueId ? ownSolvedClueIds.has(activeClueId) : false;
  const activeRejection = activeClueId
    ? (playerRejected ?? []).find((entry) => entry.clueId === activeClueId) ?? null
    : null;
  const [seenRejections, setSeenRejections] = useState<string[]>([]);
  useEffect(() => {
    setSeenRejections(loadSeenRejections(roomId));
  }, [roomId]);
  const markRejectionSeen = useCallback(
    (submissionId: string) => {
      setSeenRejections((prev) => {
        if (prev.includes(submissionId)) return prev;
        const next = [...prev, submissionId].slice(-100);
        try {
          window.localStorage.setItem(rejectionSeenKey(roomId), JSON.stringify(next));
        } catch {
          // Storage can be unavailable in private mode; the message still hides.
        }
        return next;
      });
    },
    [roomId],
  );
  const showRejection =
    activeRejection !== null && !seenRejections.includes(activeRejection.submissionId);
  const rejectionSubmissionId = activeRejection?.submissionId ?? null;
  useEffect(() => {
    if (!showRejection || rejectionSubmissionId === null) return;
    const timer = window.setTimeout(
      () => markRejectionSeen(rejectionSubmissionId),
      8000,
    );
    return () => window.clearTimeout(timer);
  }, [showRejection, rejectionSubmissionId, markRejectionSeen]);
  const isComplete =
    activeCells.length > 0 &&
    activeCells.every((cell) => (letters[cellKey(cell.row, cell.col)] ?? "").trim().length > 0);

  useEffect(() => {
    if (!liveEvent) return;
    if (lastProcessedEventRef.current === liveEvent) return;
    lastProcessedEventRef.current = liveEvent;

    try {
      if (liveEvent.type === "CLUE_SOLVED") {
        const { clueId, firstSolverColor } = liveEvent;
        setSolvedClues((prev) => {
          if (prev[clueId] !== undefined) return prev;
          return { ...prev, [clueId]: firstSolverColor };
        });
      }
    } catch {
      // ignore malformed events; letters are never touched by live events
    }
  }, [liveEvent]);

  useEffect(() => {
    setSolvedClues(initialSolvedClues);
  }, [initialSolvedClues]);

  useEffect(() => {
    if (!initialAnswers) return;
    const entries = Object.entries(initialAnswers);
    if (entries.length === 0) return;
    setLetters((prev) => {
      const next = { ...prev };
      for (const [clueId, answer] of entries) {
        const clue = puzzle.clues.find((entry) => entry.clueId === clueId);
        if (!clue) continue;
        cellsForClue(grid, clue).forEach((cell, index) => {
          const char = answer[index];
          if (char) next[cellKey(cell.row, cell.col)] = char.toUpperCase();
        });
      }
      return next;
    });
  }, [initialAnswers, grid, puzzle.clues]);

  useEffect(() => {
    setFeedback(null);
    setLastPoints(null);
    setError(null);
    if (!activeClueId || !selectedCell) {
      setNextWriteIndex(0);
      return;
    }
    const clue = puzzle.clues.find((entry) => entry.clueId === activeClueId);
    if (!clue) return;
    const cells = cellsForClue(grid, clue);
    const index = cells.findIndex(
      (cell) => cell.row === selectedCell.row && cell.col === selectedCell.col,
    );
    setNextWriteIndex(index >= 0 ? index : 0);
  }, [activeClueId]);

  useEffect(() => {
    return () => {
      if (shakeTimeout.current) clearTimeout(shakeTimeout.current);
    };
  }, []);

  const selectCell = (row: number, col: number, cell: Cell) => {
    if (selectedCell?.row === row && selectedCell?.col === col) return;
    handleCellClick(row, col, cell);
  };

  const handleCellSelect = (row: number, col: number, cell: Cell) => {
    const isSame = selectedCell?.row === row && selectedCell?.col === col;
    if (isSame) {
      const canToggle =
        Boolean(clueThrough(row, col, "across")) && Boolean(clueThrough(row, col, "down"));
      handleCellClick(row, col, cell, canToggle);
      return;
    }

    let direction = currentDirection;
    if (!clueThrough(row, col, direction)) {
      const other: Direction = direction === "across" ? "down" : "across";
      if (clueThrough(row, col, other)) direction = other;
    }
    if (direction !== currentDirection) setDirection(direction);

    const clue = clueThrough(row, col, direction);
    const cells = clue ? cellsForClue(grid, clue) : [];
    const index = cells.findIndex((entry) => entry.row === row && entry.col === col);
    setNextWriteIndex(index >= 0 ? index : 0);
    setFeedback(null);
    setError(null);
    handleCellClick(row, col, cell);
  };

  const writeLetter = (letter: string) => {
    if (!activeClue || !activeClueId || isPaused) return;
    const cells = activeCells;
    if (cells.length === 0) return;

    let index = nextWriteIndex;
    if (index < 0 || index >= cells.length) {
      index = selectedIndex >= 0 ? selectedIndex : 0;
    }
    const target = cells[index];
    setLetters((prev) => ({ ...prev, [cellKey(target.row, target.col)]: letter }));
    setFeedback(null);
    setLastPoints(null);
    setNextWriteIndex(Math.min(index + 1, cells.length - 1));
    selectCell(target.row, target.col, target);
  };

  const eraseLetter = () => {
    if (!activeClue || !activeClueId || isPaused) return;
    const cells = activeCells;
    if (cells.length === 0) return;

    const index = selectedIndex >= 0 ? selectedIndex : nextWriteIndex;
    const current = cells[index];
    if (current && letters[cellKey(current.row, current.col)]) {
      setLetters((prev) => {
        const next = { ...prev };
        delete next[cellKey(current.row, current.col)];
        return next;
      });
      setNextWriteIndex(index);
      const previous = cells[Math.max(index - 1, 0)];
      if (previous && index > 0) selectCell(previous.row, previous.col, previous);
    } else if (index > 0) {
      const previous = cells[index - 1];
      if (letters[cellKey(previous.row, previous.col)]) {
        setLetters((prev) => {
          const next = { ...prev };
          delete next[cellKey(previous.row, previous.col)];
          return next;
        });
      }
      setNextWriteIndex(index - 1);
      selectCell(previous.row, previous.col, previous);
    }
    setFeedback(null);
  };

  const moveSelection = (row: number, col: number) => {
    const cell = grid[row]?.[col];
    if (!cell || cell.type === "black" || !selectedCell) return;

    const direction: Direction = row !== selectedCell.row ? "down" : "across";
    let targetDirection = direction;
    if (!clueThrough(row, col, targetDirection)) {
      const other: Direction = targetDirection === "across" ? "down" : "across";
      if (clueThrough(row, col, other)) targetDirection = other;
    }
    if (targetDirection !== currentDirection) setDirection(targetDirection);

    const clue = clueThrough(row, col, targetDirection);
    const cells = clue ? cellsForClue(grid, clue) : [];
    const index = cells.findIndex((entry) => entry.row === row && entry.col === col);
    setNextWriteIndex(index >= 0 ? index : 0);
    handleCellClick(row, col, cell);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (isPaused || !selectedCell) return;

    if (e.key === "Enter") {
      if (!activeClueId) return;
      e.preventDefault();
      void submit();
      return;
    }
    if (
      e.key === "ArrowLeft" ||
      e.key === "ArrowRight" ||
      e.key === "ArrowUp" ||
      e.key === "ArrowDown"
    ) {
      e.preventDefault();
      const delta =
        e.key === "ArrowLeft" ? { row: 0, col: -1 }
        : e.key === "ArrowRight" ? { row: 0, col: 1 }
        : e.key === "ArrowUp" ? { row: -1, col: 0 }
        : { row: 1, col: 0 };
      setFeedback(null);
      moveSelection(selectedCell.row + delta.row, selectedCell.col + delta.col);
      return;
    }
    if (e.ctrlKey || e.metaKey || e.altKey) return;

    if (e.key.length === 1 && e.key !== " ") {
      e.preventDefault();
      writeLetter(e.key.toUpperCase());
      return;
    }
    if (e.key === "Backspace") {
      if (nextWriteIndex < 0 && selectedIndex < 0) return;
      e.preventDefault();
      eraseLetter();
    }
  };

  const submit = useCallback(async () => {
    if (!activeClueId || submitting || isRevealed || isPaused) return;
    if (!isComplete) return;

    const answer = activeCells
      .map((cell) => letters[cellKey(cell.row, cell.col)] ?? "")
      .join("")
      .trim();
    if (answer.length === 0) return;

    setSubmitting(true);
    setError(null);
    setLastPoints(null);
    try {
      const res = await roomFetch(
        roomId,
        `/rooms/${roomId}/clues/${activeClueId}/submissions`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ answer }),
        },
      );
      if (!res.ok) {
        setError(`Submission failed (status ${res.status})`);
        return;
      }
      const body = (await res.json()) as { status?: string; points?: number };
      if (
        body.status === "correct" ||
        body.status === "incorrect" ||
        body.status === "pending"
      ) {
        setFeedback(body.status);
        setLastPoints(
          body.status === "correct" && typeof body.points === "number"
            ? body.points
            : null,
        );
        if (body.status === "correct") onClueSolved?.(activeClueId);
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
  }, [
    activeClueId,
    activeCells,
    letters,
    isComplete,
    roomId,
    submitting,
    isRevealed,
    isPaused,
    onClueSolved,
  ]);

  const reveal = useCallback(async () => {
    if (!activeClueId || revealing || isRevealed || isPaused || isOwnSolved) return;
    const clueLabel = activeClue
      ? `${activeClue.number} ${activeClue.direction === "across" ? "Across" : "Down"}`
      : "this clue";
    const confirmed = window.confirm(
      `Reveal ${clueLabel}? You will not earn points for this clue.`,
    );
    if (!confirmed) return;

    setRevealing(true);
    setError(null);
    try {
      const res = await roomFetch(
        roomId,
        `/rooms/${roomId}/clues/${activeClueId}/reveal`,
        {
          method: "POST",
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
      const answer = body.answer;
      setLetters((prev) => {
        const next = { ...prev };
        activeCells.forEach((cell, index) => {
          const char = answer[index];
          if (char) next[cellKey(cell.row, cell.col)] = char.toUpperCase();
        });
        return next;
      });
      setRevealedClues((prev) => ({ ...prev, [activeClueId]: true }));
      setNextWriteIndex(Math.max(activeCells.length - 1, 0));
      onClueRevealed?.(activeClueId);
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setRevealing(false);
    }
  }, [
    activeClueId,
    activeCells,
    revealing,
    isRevealed,
    roomId,
    isOwnSolved,
    isPaused,
    onClueRevealed,
  ]);

  const solvedColorsForCell = (cell: Cell): string[] => {
    const clueIds = [
      clueThrough(cell.row, cell.col, "across")?.clueId,
      clueThrough(cell.row, cell.col, "down")?.clueId,
    ];
    const colors = clueIds
      .map((clueId) => (clueId ? solvedClues[clueId] : undefined))
      .filter((color): color is string => Boolean(color));
    return Array.from(new Set(colors));
  };

  const solvedCellStyle = (cell: Cell, colors: string[]): CSSProperties | undefined => {
    if (cell.type === "black" || colors.length === 0) return undefined;

    const outline = `inset 0 0 0 2px ${softColor(colors[0], 0.55)}`;
    const isSelected =
      selectedCell != null && selectedCell.row === cell.row && selectedCell.col === cell.col;
    const isActive = activeCellKeys.has(cellKey(cell.row, cell.col));
    const showFeedback =
      isActive &&
      (feedback === "correct" || feedback === "incorrect" || feedback === "pending");

    if (showFeedback || isSelected) {
      return { boxShadow: outline };
    }
    if (colors.length === 1) {
      return {
        backgroundColor: softColor(colors[0], 0.28),
        boxShadow: outline,
      };
    }
    const first = softColor(colors[0], 0.28);
    const second = softColor(colors[1], 0.28);
    return {
      backgroundImage: `linear-gradient(135deg, ${first} 0%, ${first} 50%, ${second} 50%, ${second} 100%)`,
      boxShadow: outline,
    };
  };

  const cellClass = (cell: Cell): string => {
    const base =
      "relative flex aspect-square w-full min-w-0 items-center justify-center border-2 text-xs font-semibold sm:text-sm";
    if (cell.type === "black") {
      return `${base} border-blue-500/60 bg-blue-400`;
    }
    const isSelected =
      selectedCell != null && selectedCell.row === cell.row && selectedCell.col === cell.col;
    const isActive = activeCellKeys.has(cellKey(cell.row, cell.col));
    let classes = `${base} border-blue-400/70 bg-white text-blue-900`;
    if (isSelected) classes += " bg-blue-200";
    else if (isActive) classes += " bg-blue-50";
    if (feedback === "correct" && isActive) classes += " bg-green-400";
    if (feedback === "incorrect" && isActive) classes += " bg-red-400 animate-[shake_0.5s_ease-in-out]";
    if (feedback === "pending" && isActive) classes += " bg-yellow-200";
    const clueIdForCell = clueThrough(cell.row, cell.col, "across")?.clueId ??
      clueThrough(cell.row, cell.col, "down")?.clueId;
    if (clueIdForCell && revealedClues[clueIdForCell] && isActive) {
      classes += " text-amber-700";
    }
    return classes;
  };

  return (
    <div
      className="flex flex-col gap-4 rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
      tabIndex={0}
      onKeyDown={handleKeyDown}
      role="application"
      aria-label="Crossword grid"
    >
      <div
        dir="ltr"
        className="mx-auto grid w-full max-w-xl gap-0"
        style={{ gridTemplateColumns: `repeat(${puzzle.width}, minmax(0, 1fr))` }}
      >
        {grid.map((row) =>
          row.map((cell) => {
            const letter = letters[cellKey(cell.row, cell.col)] ?? "";
            const solvedColors = solvedColorsForCell(cell);
            const solvedLabel = solvedColors.length > 0 ? ", solved clue" : "";
            const cellLabel =
              cell.type === "black"
                ? `Cell row ${cell.row + 1}, column ${cell.col + 1}, black square`
                : `Cell row ${cell.row + 1}, column ${cell.col + 1}, letter ${letter || "empty"}${solvedLabel}`;
            return (
              <button
                key={cellKey(cell.row, cell.col)}
                type="button"
                data-testid={`cell-${cell.row}-${cell.col}`}
                aria-label={cellLabel}
                className={cellClass(cell)}
                style={solvedCellStyle(cell, solvedColors)}
                onClick={() => handleCellSelect(cell.row, cell.col, cell)}
                disabled={cell.type === "black"}
              >
                {cell.number != null ? (
                  <span className="absolute left-0.5 top-0 text-[8px] text-blue-500">
                    {cell.number}
                  </span>
                ) : null}
                {letter}
              </button>
            );
          }),
        )}
      </div>

      <section className="glass-soft flex flex-col gap-2 p-4">
        {activeClue ? (
          <>
            <h2 className="text-lg font-semibold text-blue-800">
              {activeClue.number} {activeClue.direction === "across" ? "Across" : "Down"}
            </h2>
            <p className="text-sm text-blue-800/80">
              {activeClue.text
                ? activeClue.text
                : `${activeClue.answerLength} letters - type on the grid`}
            </p>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => void submit()}
                disabled={isRevealed || isPaused || !isComplete || submitting}
                className="btn-primary"
              >
                {submitting ? "Submitting..." : "Submit"}
              </button>
              <button
                type="button"
                onClick={() => void reveal()}
                disabled={isRevealed || isPaused || revealing || isOwnSolved}
                title={
                  isOwnSolved
                    ? "You already solved this clue"
                    : activeClue
                    ? `Reveal ${activeClue.number} ${
                        activeClue.direction === "across" ? "Across" : "Down"
                      }`
                    : "Reveal Answer"
                }
                className="btn-ghost"
              >
                {revealing ? "Revealing..." : "Reveal Answer"}
              </button>
              {isRevealed ? (
                <span role="status" className="text-sm font-medium text-amber-700">
                  Revealed - no points for this clue. You can still edit the letters locally.
                </span>
              ) : null}
              {feedback === "correct" ? (
                <span className="flex items-center gap-2">
                  <span role="status" className="text-sm font-medium text-green-700">
                    Correct!
                  </span>
                  {lastPoints !== null ? (
                    <span className="text-sm font-semibold text-green-700">
                      +{lastPoints} points
                    </span>
                  ) : null}
                </span>
              ) : null}
              {feedback === "incorrect" ? (
                <span role="status" className="text-sm font-medium text-red-700">
                  Incorrect, try again
                </span>
              ) : null}
              {showRejection ? (
                <span role="status" className="text-sm font-medium text-amber-800">
                  Admin rejected your answer for this clue. Try again.
                </span>
              ) : null}
              {feedback === "pending" && !showRejection ? (
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
          <p className="muted text-sm">Select a cell to see a clue.</p>
        )}
      </section>
    </div>
  );
}

"use client";

import { CSSProperties, KeyboardEvent, useMemo, useState } from "react";
import type { Clue, Puzzle } from "@/components/CrosswordGrid";
import { build2DGrid, type Cell } from "@/utils/grid";
import { cellKey, cellsForClue, softColor } from "@/utils/crossword";
import { adminFetch } from "@/lib/auth";

type Direction = "across" | "down";

interface AdminCrosswordProps {
  puzzle: Puzzle;
  solvedClues?: Record<string, string>;
  officialAnswers?: Record<string, string>;
  onApproved?: () => void | Promise<void>;
}

function normalizeAnswer(value: string | undefined): string {
  return (value ?? "").replace(/\s+/g, "").toUpperCase();
}

export default function AdminCrossword({
  puzzle,
  solvedClues = {},
  officialAnswers = {},
  onApproved,
}: AdminCrosswordProps) {
  const grid = useMemo(
    () => build2DGrid(puzzle.cells, puzzle.width, puzzle.height),
    [puzzle.cells, puzzle.width, puzzle.height],
  );

  const [selectedCell, setSelectedCell] = useState<{ row: number; col: number } | null>(null);
  const [direction, setDirection] = useState<Direction>("across");
  const [letters, setLetters] = useState<Record<string, string>>({});
  const [nextWriteIndex, setNextWriteIndex] = useState(0);
  const [approving, setApproving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const officialLetters = useMemo(() => {
    const result: Record<string, string> = {};
    for (const clue of puzzle.clues) {
      const answer = normalizeAnswer(officialAnswers[clue.clueId]);
      if (!answer) continue;
      cellsForClue(grid, clue).forEach((cell, index) => {
        const character = answer[index];
        if (character) result[cellKey(cell.row, cell.col)] = character;
      });
    }
    return result;
  }, [grid, officialAnswers, puzzle.clues]);

  const clueAt = (row: number, col: number, dir: Direction): Clue | undefined =>
    puzzle.clues.find(
      (clue) =>
        clue.direction === dir &&
        cellsForClue(grid, clue).some((cell) => cell.row === row && cell.col === col),
    );

  const activeClue = selectedCell
    ? clueAt(selectedCell.row, selectedCell.col, direction) ??
      clueAt(
        selectedCell.row,
        selectedCell.col,
        direction === "across" ? "down" : "across",
      ) ??
      null
    : null;
  const activeCells = activeClue ? cellsForClue(grid, activeClue) : [];
  const activeCellKeys = new Set(activeCells.map((cell) => cellKey(cell.row, cell.col)));
  const activeAnswer = activeCells
    .map(
      (cell) =>
        officialLetters[cellKey(cell.row, cell.col)] ??
        letters[cellKey(cell.row, cell.col)] ??
        "",
    )
    .join("");
  const activeApproved = activeClue
    ? normalizeAnswer(officialAnswers[activeClue.clueId]).length > 0
    : false;
  const activeSolvedColor = activeClue ? solvedClues[activeClue.clueId] : undefined;

  const handleCellSelect = (row: number, col: number, cell: Cell) => {
    if (cell.type === "black") return;
    const hasAcross = Boolean(clueAt(row, col, "across"));
    const hasDown = Boolean(clueAt(row, col, "down"));
    if (!hasAcross && !hasDown) return;

    let nextDirection = direction;
    if (!clueAt(row, col, nextDirection)) {
      nextDirection = hasAcross ? "across" : "down";
    }

    const isSame = selectedCell?.row === row && selectedCell?.col === col;
    if (isSame) {
      if (hasAcross && hasDown) {
        nextDirection = direction === "across" ? "down" : "across";
      }
    } else {
      setSelectedCell({ row, col });
    }

    setDirection(nextDirection);
    const clue = clueAt(row, col, nextDirection);
    const cells = clue ? cellsForClue(grid, clue) : [];
    const index = cells.findIndex((entry) => entry.row === row && entry.col === col);
    setNextWriteIndex(index >= 0 ? index : 0);
    setError(null);
    setNotice(null);
  };

  const writeLetter = (letter: string) => {
    if (!activeClue || activeApproved) return;
    const cells = activeCells;
    if (cells.length === 0) return;

    let index = nextWriteIndex;
    if (index < 0 || index >= cells.length) index = 0;
    const target = cells[index];
    setLetters((prev) => ({ ...prev, [cellKey(target.row, target.col)]: letter }));
    setSelectedCell({ row: target.row, col: target.col });
    setNextWriteIndex(Math.min(index + 1, cells.length - 1));
    setError(null);
    setNotice(null);
  };

  const eraseLetter = () => {
    if (!activeClue || activeApproved) return;
    const cells = activeCells;
    if (cells.length === 0) return;
    const selectedIndex = selectedCell
      ? cells.findIndex(
          (cell) => cell.row === selectedCell.row && cell.col === selectedCell.col,
        )
      : -1;
    const index = selectedIndex >= 0 ? selectedIndex : nextWriteIndex;
    const target = cells[Math.max(index, 0)];
    if (!target) return;

    setLetters((prev) => {
      const next = { ...prev };
      delete next[cellKey(target.row, target.col)];
      return next;
    });
    setNextWriteIndex(Math.max(index - 1, 0));
    setSelectedCell({ row: target.row, col: target.col });
    setError(null);
    setNotice(null);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (!selectedCell || event.ctrlKey || event.metaKey || event.altKey) return;

    if (event.key === "Enter") {
      event.preventDefault();
      void approve();
      return;
    }
    if (event.key === "Backspace") {
      event.preventDefault();
      eraseLetter();
      return;
    }
    if (event.key.length === 1 && event.key !== " ") {
      event.preventDefault();
      writeLetter(event.key.toUpperCase());
    }
  };

  async function approve() {
    if (!activeClue || activeApproved || approving) return;
    if (activeAnswer.length !== activeClue.answerLength) {
      setError("Fill the whole clue before approving.");
      return;
    }

    const confirmed = window.confirm(
      `Approve "${activeAnswer}" for clue ${activeClue.number} ${
        activeClue.direction === "across" ? "Across" : "Down"
      }?`,
    );
    if (!confirmed) return;

    setApproving(true);
    setError(null);
    setNotice(null);
    try {
      const res = await adminFetch(
        `/admin/puzzles/${puzzle.puzzleId}/clues/${activeClue.clueId}/answer`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ answer: activeAnswer }),
        },
      );
      if (!res.ok) {
        setError(`Failed to approve clue (status ${res.status})`);
        return;
      }
      setNotice(
        "Answer approved. Players will see the first solver's color when the clue is solved.",
      );
      await onApproved?.();
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setApproving(false);
    }
  }

  const colorsForCell = (cell: Cell): string[] => {
    const clueIds = [
      clueAt(cell.row, cell.col, "across")?.clueId,
      clueAt(cell.row, cell.col, "down")?.clueId,
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
    if (isSelected || isActive) {
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
    if (cell.type === "black") return `${base} border-blue-500/60 bg-blue-400`;
    const isSelected =
      selectedCell != null && selectedCell.row === cell.row && selectedCell.col === cell.col;
    const isActive = activeCellKeys.has(cellKey(cell.row, cell.col));
    let classes = `${base} border-blue-400/70 bg-white text-blue-900`;
    if (isSelected) classes += " bg-blue-200";
    else if (isActive) classes += " bg-blue-50";
    return classes;
  };

  return (
    <div
      className="flex flex-col gap-4 rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
      tabIndex={0}
      onKeyDown={handleKeyDown}
      role="application"
      aria-label="Admin crossword grid"
    >
      <div
        dir="ltr"
        className="mx-auto grid w-full max-w-xl gap-0"
        style={{ gridTemplateColumns: `repeat(${puzzle.width}, minmax(0, 1fr))` }}
      >
        {grid.map((row) =>
          row.map((cell) => {
            const key = cellKey(cell.row, cell.col);
            const letter = officialLetters[key] ?? letters[key] ?? "";
            const colors = colorsForCell(cell);
            const cellLabel =
              cell.type === "black"
                ? `Cell row ${cell.row + 1}, column ${cell.col + 1}, black square`
                : `Cell row ${cell.row + 1}, column ${cell.col + 1}, letter ${letter || "empty"}${colors.length ? ", solved clue" : ""}`;
            return (
              <button
                key={key}
                type="button"
                data-testid={`admin-cell-${cell.row}-${cell.col}`}
                aria-label={cellLabel}
                className={cellClass(cell)}
                style={solvedCellStyle(cell, colors)}
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
            {activeApproved ? (
              <p className="text-sm font-medium text-emerald-700">
                Approved
                {activeSolvedColor
                  ? " and solved. The clue is colored for the first solver."
                  : " - waiting for the first correct player submission."}
              </p>
            ) : (
              <p className="muted text-sm">
                Private admin draft. Players cannot see these letters until a player answers
                correctly.
              </p>
            )}
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => void approve()}
                disabled={
                  activeApproved ||
                  approving ||
                  activeAnswer.length !== activeClue.answerLength
                }
                className="btn-primary"
              >
                {approving ? "Approving..." : "Approve answer"}
              </button>
              {activeApproved && activeSolvedColor ? (
                <span
                  className="inline-block h-4 w-8 rounded-full border border-blue-900/20"
                  style={{ backgroundColor: softColor(activeSolvedColor, 0.6) }}
                  aria-label="First solver color"
                />
              ) : null}
            </div>
            {notice ? (
              <p role="status" className="text-sm font-medium text-emerald-700">
                {notice}
              </p>
            ) : null}
            {error ? (
              <p role="alert" className="text-sm text-red-600">
                {error}
              </p>
            ) : null}
          </>
        ) : (
          <p className="muted text-sm">Select a cell to draft and approve a clue.</p>
        )}
      </section>
    </div>
  );
}

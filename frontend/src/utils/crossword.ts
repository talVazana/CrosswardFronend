import type { Cell } from "./grid";

export interface CrosswordClue {
  clueId: string;
  number: number;
  direction: "across" | "down";
  text: string;
  answerLength: number;
}

export function cellKey(row: number, col: number): string {
  return `${row}-${col}`;
}

export function softColor(color: string, alpha: number): string {
  const match = /^#([0-9a-fA-F]{6})$/.exec(color);
  if (!match) return `rgba(37, 99, 235, ${alpha})`;
  const value = parseInt(match[1], 16);
  const red = (value >> 16) & 0xff;
  const green = (value >> 8) & 0xff;
  const blue = value & 0xff;
  return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
}

export function cellsForClue(grid: Cell[][], clue: CrosswordClue): Cell[] {
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
      const step = clue.direction === "across" ? -1 : 0;
      const stepRow = clue.direction === "down" ? 1 : 0;
      for (let i = 0; i < clue.answerLength; i++) {
        const next = grid[r]?.[c];
        if (!next || next.type === "black") break;
        cells.push(next);
        r += stepRow;
        c += step;
      }
      return cells;
    }
  }
  return cells;
}

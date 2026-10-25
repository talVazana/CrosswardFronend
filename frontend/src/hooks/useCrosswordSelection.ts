"use client";

import { useState } from "react";
import type { Cell } from "../utils/grid";

export type Direction = "across" | "down";

export interface SelectedCell {
  row: number;
  col: number;
}

export interface UseCrosswordSelectionResult {
  selectedCell: SelectedCell | null;
  currentDirection: Direction;
  handleCellClick: (row: number, col: number, cell: Cell, canToggle?: boolean) => void;
  setDirection: (dir: Direction) => void;
}

function supportsBothDirections(cell: Cell): boolean {
  return cell.startsAcross && cell.startsDown;
}

export function useCrosswordSelection(): UseCrosswordSelectionResult {
  const [selectedCell, setSelectedCell] = useState<SelectedCell | null>(null);
  const [currentDirection, setCurrentDirection] = useState<Direction>("across");

  const handleCellClick = (
    row: number,
    col: number,
    cell: Cell,
    canToggle: boolean = supportsBothDirections(cell),
  ) => {
    if (cell.type === "black") {
      return;
    }

    if (selectedCell && selectedCell.row === row && selectedCell.col === col) {
      if (canToggle) {
        setCurrentDirection((dir) => (dir === "across" ? "down" : "across"));
      }
      return;
    }

    setSelectedCell({ row, col });
  };

  const setDirection = (dir: Direction) => {
    setCurrentDirection(dir);
  };

  return {
    selectedCell,
    currentDirection,
    handleCellClick,
    setDirection,
  };
}

export default useCrosswordSelection;

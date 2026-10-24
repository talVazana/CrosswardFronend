import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import CrosswordGrid, { Puzzle } from "../src/components/CrosswordGrid";
import ClueList from "../src/components/ClueList";

const puzzle: Puzzle = {
  puzzleId: "a11y-puzzle",
  title: "Accessibility",
  width: 3,
  height: 3,
  cells: [
    { row: 0, col: 0, type: "white", number: 1, startsAcross: true, startsDown: true },
    { row: 0, col: 1, type: "white", number: null, startsAcross: false, startsDown: false },
    { row: 0, col: 2, type: "white", number: null, startsAcross: false, startsDown: false },
    { row: 1, col: 0, type: "white", number: 2, startsAcross: false, startsDown: true },
    { row: 1, col: 1, type: "white", number: null, startsAcross: false, startsDown: false },
    { row: 1, col: 2, type: "white", number: null, startsAcross: false, startsDown: false },
    { row: 2, col: 0, type: "white", number: 3, startsAcross: true, startsDown: false },
    { row: 2, col: 1, type: "white", number: null, startsAcross: false, startsDown: false },
    { row: 2, col: 2, type: "black", number: null, startsAcross: false, startsDown: false },
  ],
  clues: [
    { clueId: "A1", number: 1, direction: "across", text: "First row", answerLength: 3 },
    { clueId: "D1", number: 1, direction: "down", text: "First column", answerLength: 3 },
  ],
};

afterEach(() => {
  cleanup();
});

describe("TASK-045 keyboard accessibility and responsive polish", () => {
  it("Given the rendered CrosswordGrid, when inspecting a white cell at row 0, col 0, then it has an aria-label describing its state", () => {
    render(<CrosswordGrid roomId="room-1" puzzle={puzzle} />);
    const cell = screen.getByTestId("cell-0-0");
    const label = cell.getAttribute("aria-label");
    expect(label).toBeTruthy();
    expect(label).toContain("row 1");
    expect(label).toContain("column 1");
    expect(label).toMatch(/empty|letter/i);
  });

  it("Given the rendered clue list, when a clue is active, then its DOM element exposes an ARIA active-state attribute", () => {
    render(<ClueList clues={puzzle.clues} activeClueId="D1" />);
    const items = screen.getAllByRole("listitem");
    const active = items.filter((item) => item.getAttribute("aria-current") === "true");
    expect(active).toHaveLength(1);
    expect(active[0].getAttribute("aria-label")).toContain("Down");
  });

  it("Given the main grid container, when inspecting its attributes, then it has tabIndex={0}", () => {
    render(<CrosswordGrid roomId="room-1" puzzle={puzzle} />);
    const container = screen.getByRole("application", { name: "Crossword grid" });
    expect(container.getAttribute("tabindex")).toBe("0");
  });

  it("Edge case: black cells are either aria-hidden or carry a descriptive black-cell label", () => {
    render(<CrosswordGrid roomId="room-1" puzzle={puzzle} />);
    const black = screen.getByTestId("cell-2-2");
    const hidden = black.getAttribute("aria-hidden") === "true" && black.getAttribute("aria-label") === "";
    const labelled = /black/i.test(black.getAttribute("aria-label") ?? "");
    expect(hidden || labelled).toBe(true);
  });

  it("Acceptance: keyboard focus is visibly distinct when tabbing into the crossword grid", () => {
    render(<CrosswordGrid roomId="room-1" puzzle={puzzle} />);
    const container = screen.getByRole("application", { name: "Crossword grid" });
    const classes = container.className;
    expect(classes).toMatch(/focus-visible:/);
    expect(classes).toMatch(/(ring|outline)/);
  });

  it("Acceptance: narrow-viewport safeguards prevent horizontal overflow of the main document body", () => {
    const css = readFileSync(resolve(__dirname, "../src/app/globals.css"), "utf8");
    expect(css).toMatch(/html,\s*body\s*\{[^}]*overflow-x:\s*hidden/s);
    expect(css).toMatch(/max-width:\s*100%/);
    const page = readFileSync(
      resolve(__dirname, "../src/app/rooms/[roomId]/page.tsx"),
      "utf8",
    );
    expect(page).toMatch(/overflow-x-hidden/);
  });
});

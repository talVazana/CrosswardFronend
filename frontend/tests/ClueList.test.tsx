import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import ClueList from "../src/components/ClueList";
import type { Clue } from "../src/components/CrosswordGrid";

const clues: Clue[] = [
  { clueId: "A1", number: 1, direction: "across", text: "Fruit", answerLength: 5 },
  { clueId: "D1", number: 1, direction: "down", text: "Drink", answerLength: 5 },
];

afterEach(() => {
  cleanup();
});

describe("ClueList submitted/draft indicator", () => {
  it("shows Submitted and Draft tags in admin context", () => {
    render(<ClueList clues={clues} submittedClueIds={new Set(["A1"])} />);

    expect(screen.getByText("Submitted")).toBeTruthy();
    expect(screen.getByText("Draft")).toBeTruthy();
  });

  it("shows no tags in player context", () => {
    render(<ClueList clues={clues} />);

    expect(screen.queryByText("Submitted")).toBeNull();
    expect(screen.queryByText("Draft")).toBeNull();
  });
});

import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/react";
import AdminCrossword from "../src/components/AdminCrossword";
import type { Puzzle } from "../src/components/CrosswordGrid";

const puzzle: Puzzle = {
  puzzleId: "puzzle-1",
  title: "Admin",
  width: 3,
  height: 1,
  cells: [
    { row: 0, col: 0, type: "white", number: null, startsAcross: false, startsDown: false },
    { row: 0, col: 1, type: "white", number: null, startsAcross: false, startsDown: false },
    { row: 0, col: 2, type: "white", number: 1, startsAcross: true, startsDown: false },
  ],
  clues: [
    { clueId: "A1", number: 1, direction: "across", text: "Feline pet", answerLength: 3 },
  ],
};

function typeWord(word: string) {
  const grid = screen.getByRole("application", { name: "Admin crossword grid" });
  for (const letter of word) {
    fireEvent.keyDown(grid, { key: letter });
  }
}

function okResponse(body: unknown = { status: "ok" }) {
  return {
    ok: true,
    status: 200,
    json: async () => body,
  } as unknown as Response;
}

beforeEach(() => {
  vi.stubGlobal("confirm", vi.fn(() => true));
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Admin crossword drafting and approval", () => {
  it("shows approved solution letters and applies the first solver color", () => {
    render(
      <AdminCrossword
        puzzle={puzzle}
        officialAnswers={{ A1: "CAT" }}
        solvedClues={{ A1: "#F87171" }}
      />,
    );

    expect(screen.getByTestId("admin-cell-0-2").textContent).toContain("C");
    expect(screen.getByTestId("admin-cell-0-1").textContent).toContain("A");
    expect(screen.getByTestId("admin-cell-0-0").textContent).toContain("T");
    expect(
      (screen.getByTestId("admin-cell-0-0") as HTMLElement).style.backgroundColor,
    ).toMatch(/rgba\(248,\s*113,\s*113/i);
  });

  it("lets the admin draft a clue and approve it without submitting as a player", async () => {
    const mockFetch = vi.fn().mockResolvedValue(okResponse());
    const onApproved = vi.fn();
    vi.stubGlobal("fetch", mockFetch);

    render(<AdminCrossword puzzle={puzzle} onApproved={onApproved} />);
    fireEvent.click(screen.getByTestId("admin-cell-0-2"));
    typeWord("CAT");

    const approve = screen.getByRole("button", { name: "Approve answer" }) as HTMLButtonElement;
    await waitFor(() => expect(approve.disabled).toBe(false));
    fireEvent.click(approve);

    await waitFor(() => expect(mockFetch).toHaveBeenCalledTimes(1));
    const [url, init] = mockFetch.mock.calls[0];
    expect(String(url)).toContain("/admin/puzzles/puzzle-1/clues/A1/answer");
    expect(init.method).toBe("PUT");
    expect(init.credentials).toBe("include");
    expect(JSON.parse(init.body)).toEqual({ answer: "CAT" });
    await waitFor(() => expect(onApproved).toHaveBeenCalledTimes(1));
  });

  it("does not approve a partially filled clue", () => {
    vi.stubGlobal("fetch", vi.fn());
    render(<AdminCrossword puzzle={puzzle} />);
    fireEvent.click(screen.getByTestId("admin-cell-0-2"));

    expect(
      (screen.getByRole("button", { name: "Approve answer" }) as HTMLButtonElement).disabled,
    ).toBe(true);
  });

  it("keeps an approved clue read-only", () => {
    vi.stubGlobal("fetch", vi.fn());
    render(<AdminCrossword puzzle={puzzle} officialAnswers={{ A1: "CAT" }} />);
    fireEvent.click(screen.getByTestId("admin-cell-0-2"));

    typeWord("DOG");
    expect(screen.getByTestId("admin-cell-0-2").textContent).toContain("C");
    expect(
      (screen.getByRole("button", { name: "Approve answer" }) as HTMLButtonElement).disabled,
    ).toBe(true);
  });
});

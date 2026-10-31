import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, act } from "@testing-library/react";
import CrosswordGrid, { Puzzle } from "../src/components/CrosswordGrid";

const puzzle: Puzzle = {
  puzzleId: "test-puzzle",
  title: "Test",
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

function response(status: number, body: unknown) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as unknown as Response;
}

function renderGrid() {
  const utils = render(<CrosswordGrid roomId="room-1" puzzle={puzzle} />);
  fireEvent.click(screen.getByTestId("cell-0-2"));
  return utils;
}

function typeWord(word: string) {
  const grid = screen.getByRole("application", { name: "Crossword grid" });
  for (const letter of word) {
    fireEvent.keyDown(grid, { key: letter });
  }
}

function getSubmit(): HTMLButtonElement {
  return screen.getByRole("button", { name: "Submit" }) as HTMLButtonElement;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  window.localStorage.clear();
});

describe("TASK-025 submission UI", () => {
  it("empty grid: Submit button is disabled", () => {
    renderGrid();
    expect(getSubmit().disabled).toBe(true);
  });

  it("empty grid: pressing Enter does not fire fetch", async () => {
    const mockFetch = vi.fn();
    vi.stubGlobal("fetch", mockFetch);
    renderGrid();
    const grid = screen.getByRole("application", { name: "Crossword grid" });
    fireEvent.keyDown(grid, { key: "Enter", code: "Enter" });
    await new Promise((r) => setTimeout(r, 50));
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("typing letters on the grid fills the clue cells and enables Submit", () => {
    renderGrid();
    typeWord("cat");
    expect(screen.getByTestId("cell-0-2").textContent).toContain("C");
    expect(screen.getByTestId("cell-0-1").textContent).toContain("A");
    expect(screen.getByTestId("cell-0-0").textContent).toContain("T");
    expect(getSubmit().disabled).toBe(false);
  });

  it("click Submit with correct status: shows Correct indicator", async () => {
    const mockFetch = vi.fn().mockResolvedValue(response(200, { status: "correct" }));
    vi.stubGlobal("fetch", mockFetch);
    renderGrid();
    typeWord("cat");
    fireEvent.click(getSubmit());
    expect(await screen.findByText("Correct!")).toBeTruthy();
    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, init] = mockFetch.mock.calls[0];
    expect(String(url)).toContain("/rooms/room-1/clues/A1/submissions");
    expect(init.method).toBe("POST");
    expect(init.credentials).toBe("include");
    expect(JSON.parse(init.body)).toEqual({ answer: "CAT" });
  });

  it("pressing Enter with incorrect status: shows error indicator and grid stays editable", async () => {
    const mockFetch = vi.fn().mockResolvedValue(response(200, { status: "incorrect" }));
    vi.stubGlobal("fetch", mockFetch);
    renderGrid();
    typeWord("dog");
    const grid = screen.getByRole("application", { name: "Crossword grid" });
    fireEvent.keyDown(grid, { key: "Enter", code: "Enter" });
    expect(await screen.findByText("Incorrect, try again")).toBeTruthy();
    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [, init] = mockFetch.mock.calls[0];
    expect(init.credentials).toBe("include");
    expect(JSON.parse(init.body)).toEqual({ answer: "DOG" });
    expect(getSubmit().disabled).toBe(false);
    expect(screen.getByTestId("cell-0-2").textContent).toContain("D");
  });

  it("pending status: shows Waiting for Admin indicator", async () => {
    const mockFetch = vi.fn().mockResolvedValue(response(200, { status: "pending" }));
    vi.stubGlobal("fetch", mockFetch);
    renderGrid();
    typeWord("cat");
    fireEvent.click(getSubmit());
    expect(await screen.findByText("Waiting for Admin")).toBeTruthy();
  });

  it("rejected answer shows a message that hides after a few seconds", () => {
    vi.useFakeTimers();
    try {
      render(
        <CrosswordGrid
          roomId="room-1"
          puzzle={puzzle}
          playerRejected={[{ clueId: "A1", submissionId: "sub-1" }]}
        />,
      );
      fireEvent.click(screen.getByTestId("cell-0-2"));
      expect(screen.getByText(/Admin rejected your answer/i)).toBeTruthy();

      act(() => {
        vi.advanceTimersByTime(8000);
      });

      expect(screen.queryByText(/Admin rejected your answer/i)).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it("does not show a rejection message that was already seen", () => {
    window.localStorage.setItem(
      "crossword-rejection-seen:room-1",
      JSON.stringify(["sub-1"]),
    );
    render(
      <CrosswordGrid
        roomId="room-1"
        puzzle={puzzle}
        playerRejected={[{ clueId: "A1", submissionId: "sub-1" }]}
      />,
    );
    fireEvent.click(screen.getByTestId("cell-0-2"));
    expect(screen.queryByText(/Admin rejected your answer/i)).toBeNull();
    window.localStorage.clear();
  });

  it("visual distinction: correct/incorrect/pending use different DOM indicators", async () => {
    const cases: Array<[string, string]> = [
      ["correct", "Correct!"],
      ["incorrect", "Incorrect, try again"],
      ["pending", "Waiting for Admin"],
    ];
    for (const [status, expected] of cases) {
      const mockFetch = vi.fn().mockResolvedValue(response(200, { status }));
      vi.stubGlobal("fetch", mockFetch);
      const { unmount } = renderGrid();
      typeWord("cat");
      fireEvent.click(getSubmit());
      expect(await screen.findByText(expected)).toBeTruthy();
      const cell = screen.getByTestId("cell-0-2");
      const cls = cell.className;
      if (status === "correct") expect(cls).toContain("bg-green-400");
      if (status === "incorrect") expect(cls).toContain("bg-red-400");
      if (status === "pending") expect(cls).toContain("bg-yellow-200");
      unmount();
      cleanup();
      vi.unstubAllGlobals();
    }
  });

  it("notifies the room when an approved clue is solved", async () => {
    const onClueSolved = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(response(200, { status: "correct", points: 2 })),
    );
    render(
      <CrosswordGrid
        roomId="room-1"
        puzzle={puzzle}
        onClueSolved={onClueSolved}
      />,
    );
    fireEvent.click(screen.getByTestId("cell-0-2"));
    typeWord("cat");
    fireEvent.click(getSubmit());

    await screen.findByText("Correct!");
    expect(onClueSolved).toHaveBeenCalledWith("A1");
  });

  it("does not mark a pending clue as solved for the player", async () => {
    const onClueSolved = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(response(200, { status: "pending" })),
    );
    render(
      <CrosswordGrid
        roomId="room-1"
        puzzle={puzzle}
        onClueSolved={onClueSolved}
      />,
    );
    fireEvent.click(screen.getByTestId("cell-0-2"));
    typeWord("cat");
    fireEvent.click(getSubmit());

    await screen.findByText("Waiting for Admin");
    expect(onClueSolved).not.toHaveBeenCalled();
  });

  it("network failure: shows an error message and grid remains usable", async () => {
    const mockFetch = vi.fn().mockRejectedValue(new Error("network down"));
    vi.stubGlobal("fetch", mockFetch);
    renderGrid();
    typeWord("cat");
    fireEvent.click(getSubmit());
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByRole("alert").textContent).toMatch(/network/i);
    expect(screen.getByTestId("cell-0-2")).toBeTruthy();
    expect(getSubmit().disabled).toBe(false);
  });

  it("non-ok response: shows an error message without breaking grid", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(500, {})));
    renderGrid();
    typeWord("cat");
    fireEvent.click(getSubmit());
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/failed/i);
    expect(screen.getByTestId("cell-0-2")).toBeTruthy();
  });

  it("accepts letters from the hidden input for mobile keyboards", () => {
    renderGrid();
    const input = screen.getByTestId("crossword-input");
    for (const letter of "cat") {
      fireEvent.change(input, { target: { value: letter } });
    }
    expect(screen.getByTestId("cell-0-2").textContent).toContain("C");
    expect(screen.getByTestId("cell-0-1").textContent).toContain("A");
    expect(screen.getByTestId("cell-0-0").textContent).toContain("T");
    expect(getSubmit().disabled).toBe(false);
  });

  it("activates a clue selected from the clue list", () => {
    render(
      <CrosswordGrid
        roomId="room-1"
        puzzle={puzzle}
        selectionRequest={{ clueId: "A1", nonce: 1 }}
      />,
    );
    expect(screen.getByText("1 Across")).toBeTruthy();
  });

  it("converts Hebrew final letters to regular letters on input", () => {
    renderGrid();
    const input = screen.getByTestId("crossword-input");
    fireEvent.change(input, { target: { value: "ם" } });
    fireEvent.change(input, { target: { value: "ן" } });
    fireEvent.change(input, { target: { value: "ץ" } });
    expect(screen.getByTestId("cell-0-2").textContent).toContain("מ");
    expect(screen.getByTestId("cell-0-1").textContent).toContain("נ");
    expect(screen.getByTestId("cell-0-0").textContent).toContain("צ");
  });

  it("restores a pending answer and shows Waiting for Admin", () => {
    render(
      <CrosswordGrid
        roomId="room-1"
        puzzle={puzzle}
        initialAnswers={{ A1: "CAT" }}
        playerPendingClues={["A1"]}
      />,
    );
    expect(screen.getByTestId("cell-0-2").textContent).toContain("C");
    expect(screen.getByTestId("cell-0-1").textContent).toContain("A");
    expect(screen.getByTestId("cell-0-0").textContent).toContain("T");
    fireEvent.click(screen.getByTestId("cell-0-2"));
    expect(screen.getByText("Waiting for Admin")).toBeTruthy();
    expect(getSubmit().disabled).toBe(false);
  });

  it("notifies when the player session is no longer valid", async () => {
    const onUnauthorized = vi.fn();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(401, {})));
    render(
      <CrosswordGrid
        roomId="room-1"
        puzzle={puzzle}
        onUnauthorized={onUnauthorized}
      />,
    );
    fireEvent.click(screen.getByTestId("cell-0-2"));
    typeWord("cat");
    fireEvent.click(getSubmit());
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/session expired/i);
    expect(onUnauthorized).toHaveBeenCalled();
  });
});

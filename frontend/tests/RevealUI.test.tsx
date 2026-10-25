import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/react";
import CrosswordGrid, {
  type Puzzle,
} from "../src/components/CrosswordGrid";

function makePuzzle(): Puzzle {
  const width = 5;
  const cells = Array.from({ length: width }, (_, col) => ({
    row: 0,
    col,
    type: "white",
    number: col === width - 1 ? 1 : null,
    startsAcross: col === width - 1,
    startsDown: false,
  }));
  return {
    puzzleId: "puzzle-1",
    title: "Fruit",
    width,
    height: 1,
    cells,
    clues: [
      {
        clueId: "clue-1",
        number: 1,
        direction: "across" as const,
        text: "A red or green fruit",
        answerLength: 5,
      },
    ],
  };
}

function typeWord(word: string) {
  const grid = screen.getByRole("application", { name: "Crossword grid" });
  for (const letter of word) {
    fireEvent.keyDown(grid, { key: letter });
  }
}

function renderWithActiveClue() {
  render(<CrosswordGrid roomId="room-42" puzzle={makePuzzle()} />);
  fireEvent.click(screen.getByTestId("cell-0-4"));
  return {
    revealButton: screen.getByRole("button", { name: "Reveal Answer" }),
    submitButton: screen.getByRole("button", { name: "Submit" }),
  };
}

function okReveal(answer: string) {
  return vi.fn().mockResolvedValue({
    status: 200,
    ok: true,
    json: async () => ({ answer }),
  });
}

beforeEach(() => {
  vi.stubGlobal("confirm", vi.fn(() => true));
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("TASK-031 Reveal UI", () => {
  it("Given the active clue UI, when rendered, then a Reveal Answer button is visible", () => {
    const { revealButton } = renderWithActiveClue();
    expect(revealButton).toBeTruthy();
    expect(revealButton.textContent).toBe("Reveal Answer");
  });

  it("Given the user clicks Reveal Answer, when window.confirm returns false, then fetch is never called", async () => {
    const confirmMock = vi.fn(() => false);
    vi.stubGlobal("confirm", confirmMock);
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const { revealButton } = renderWithActiveClue();
    fireEvent.click(revealButton);

    await waitFor(() => expect(confirmMock).toHaveBeenCalledTimes(1));
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("Given the user confirms reveal, when fetch resolves 200 with {answer: APPLE}, then APPLE renders in the clue's grid cells", async () => {
    const fetchMock = okReveal("APPLE");
    vi.stubGlobal("fetch", fetchMock);

    const { revealButton } = renderWithActiveClue();
    fireEvent.click(revealButton);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/rooms/room-42/clues/clue-1/reveal");
    expect(init.method).toBe("POST");
    expect(init.credentials).toBe("include");

    await waitFor(() => {
      expect(screen.getByTestId("cell-0-4").textContent).toContain("A");
    });
    expect(screen.getByTestId("cell-0-3").textContent).toContain("P");
    expect(screen.getByTestId("cell-0-2").textContent).toContain("P");
    expect(screen.getByTestId("cell-0-1").textContent).toContain("L");
    expect(screen.getByTestId("cell-0-0").textContent).toContain("E");
  });

  it("Given a successfully revealed clue, when inspecting the UI, then the Submit button is disabled", async () => {
    vi.stubGlobal("fetch", okReveal("APPLE"));

    const { revealButton } = renderWithActiveClue();
    fireEvent.click(revealButton);

    await waitFor(() => {
      expect((screen.getByRole("button", { name: "Submit" }) as HTMLButtonElement).disabled).toBe(
        true,
      );
    });
  });

  it("Given a revealed clue, when the player types, then they can edit the revealed letters locally", async () => {
    vi.stubGlobal("fetch", okReveal("APPLE"));

    const { revealButton } = renderWithActiveClue();
    fireEvent.click(revealButton);

    await waitFor(() => {
      expect(screen.getByTestId("cell-0-4").textContent).toContain("A");
    });
    typeWord("X");
    expect(screen.getByTestId("cell-0-0").textContent).toContain("X");
    expect(screen.getByTestId("cell-0-4").textContent).toContain("A");
  });

  it("notifies the room when the player reveals a clue", async () => {
    const onClueRevealed = vi.fn();
    vi.stubGlobal("fetch", okReveal("APPLE"));

    render(
      <CrosswordGrid
        roomId="room-42"
        puzzle={makePuzzle()}
        onClueRevealed={onClueRevealed}
      />,
    );
    fireEvent.click(screen.getByTestId("cell-0-4"));
    fireEvent.click(screen.getByRole("button", { name: "Reveal Answer" }));

    await waitFor(() => {
      expect(onClueRevealed).toHaveBeenCalledWith("clue-1");
    });
  });

  it("Edge: fetch resolving 400 displays an error and does not disable the Submit button", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      status: 400,
      ok: false,
      json: async () => ({ detail: "Answer not available yet" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const { revealButton, submitButton } = renderWithActiveClue();
    typeWord("GUESS");
    expect(submitButton.disabled).toBe(false);

    fireEvent.click(revealButton);

    const alert = await screen.findByRole("alert");
    expect(alert.textContent ?? "").toMatch(/answer not available yet/i);
    expect(
      (screen.getByRole("button", { name: "Submit" }) as HTMLButtonElement).disabled,
    ).toBe(false);
  });
});

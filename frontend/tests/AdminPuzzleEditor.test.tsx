import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/react";

const { mockPush } = vi.hoisted(() => ({ mockPush: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

import PuzzleEditorPage from "../src/app/admin/puzzles/editor/page";

const puzzleFixture = {
  puzzleId: "puzzle-1",
  title: "Fixture Puzzle",
  width: 3,
  height: 3,
  cells: [
    { row: 0, col: 0, type: "white", number: 1, startsAcross: true, startsDown: true },
    { row: 0, col: 1, type: "white", number: null, startsAcross: false, startsDown: false },
    { row: 0, col: 2, type: "white", number: null, startsAcross: false, startsDown: false },
    { row: 1, col: 0, type: "white", number: 2, startsAcross: false, startsDown: true },
    { row: 2, col: 0, type: "white", number: null, startsAcross: false, startsDown: false },
  ],
  clues: [
    { clueId: "A1", number: 1, direction: "across", text: "Fixture clue", answerLength: 3 },
    { clueId: "D2", number: 2, direction: "down", text: "Down clue", answerLength: 3 },
  ],
};

function response(status: number, body: unknown) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as unknown as Response;
}

type Handler = (url: string, init?: RequestInit) => Response | Promise<Response>;

function installFetch(handlers: { parse?: Handler; save?: Handler }) {
  const mockFetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith("/admin/puzzles/parse")) {
      if (!handlers.parse) throw new Error(`unexpected parse call: ${url}`);
      return handlers.parse(url, init);
    }
    if (url.endsWith("/admin/puzzles")) {
      if (!handlers.save) throw new Error(`unexpected save call: ${url}`);
      return handlers.save(url, init);
    }
    throw new Error(`unexpected fetch: ${url}`);
  });
  vi.stubGlobal("fetch", mockFetch);
  return mockFetch;
}

function callsTo(mockFetch: ReturnType<typeof vi.fn>, suffix: string) {
  return mockFetch.mock.calls.filter(([input]) => String(input).endsWith(suffix));
}

function parseInit(mockFetch: ReturnType<typeof vi.fn>) {
  const calls = callsTo(mockFetch, "/admin/puzzles/parse");
  expect(calls.length).toBe(1);
  return calls[0][1] as RequestInit;
}

async function loadFixture(handlers: { parse?: Handler; save?: Handler }) {
  const mockFetch = installFetch(handlers);
  render(<PuzzleEditorPage />);
  fireEvent.click(screen.getByRole("button", { name: /Load from Test Fixture/i }));
  return mockFetch;
}

beforeEach(() => {
  mockPush.mockReset();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("TASK-037 admin puzzle editor", () => {
  it("Given the editor page, When 'Load from Test Fixture' is clicked, Then POST /admin/puzzles/parse is sent with {use_fixture:true}", async () => {
    const mockFetch = await loadFixture({
      parse: () => response(200, { puzzle: puzzleFixture, validation_errors: [] }),
    });
    await screen.findByRole("application", { name: "Crossword grid" });
    const init = parseInit(mockFetch);
    expect(init.method).toBe("POST");
    expect(init.credentials).toBe("include");
    expect(JSON.parse(String(init.body))).toEqual({ use_fixture: true });
  });

  it("Given a valid puzzle and empty errors, When loaded, Then CrosswordGrid renders and clue answer inputs appear", async () => {
    await loadFixture({
      parse: () => response(200, { puzzle: puzzleFixture, validation_errors: [] }),
    });
    expect(await screen.findByRole("application", { name: "Crossword grid" })).toBeTruthy();
    expect(screen.getByLabelText("Official answer A1")).toBeTruthy();
    expect(screen.getByLabelText("Official answer D2")).toBeTruthy();
    expect((screen.getByLabelText("Clue text A1") as HTMLInputElement).value).toBe(
      "Fixture clue",
    );
  });

  it("Given parse resolves with validation_errors, When the component updates, Then a red alert containing the error is rendered", async () => {
    await loadFixture({
      parse: () =>
        response(200, {
          puzzle: puzzleFixture,
          validation_errors: ["Clue A1 length mismatch"],
        }),
    });
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Clue A1 length mismatch");
    expect(alert.className).toMatch(/red/);
  });

  it("Given a loaded puzzle, When the admin edits the clue text and answers and clicks 'Save Puzzle', Then POST /admin/puzzles carries combined puzzle and answers payload", async () => {
    const mockFetch = await loadFixture({
      parse: () => response(200, { puzzle: puzzleFixture, validation_errors: [] }),
      save: () => response(200, { puzzleId: "puzzle-1" }),
    });
    await screen.findByRole("application", { name: "Crossword grid" });

    fireEvent.change(screen.getByLabelText("Clue text A1"), {
      target: { value: "Edited fixture clue" },
    });
    fireEvent.change(screen.getByLabelText("Official answer A1"), {
      target: { value: "CAT" },
    });
    fireEvent.change(screen.getByLabelText("Official answer D2"), {
      target: { value: "DOG" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Save Puzzle/i }));

    await waitFor(() => expect(callsTo(mockFetch, "/admin/puzzles").length).toBe(1));
    const [, init] = callsTo(mockFetch, "/admin/puzzles")[0];
    const saveInit = init as RequestInit;
    expect(saveInit.method).toBe("POST");
    expect(saveInit.credentials).toBe("include");
    const body = JSON.parse(String(saveInit.body));
    expect(body.puzzle.puzzleId).toBe("puzzle-1");
    expect(body.puzzle.clues.find((c: { clueId: string }) => c.clueId === "A1").text).toBe(
      "Edited fixture clue",
    );
    expect(body.officialAnswers.answers).toEqual({ A1: "CAT", D2: "DOG" });
    await waitFor(() => expect(mockPush).toHaveBeenCalledWith("/admin/rooms"));
  });

  it("Given save returns server validation errors, When Save Puzzle is clicked, Then the errors are visibly rendered", async () => {
    await loadFixture({
      parse: () => response(200, { puzzle: puzzleFixture, validation_errors: [] }),
      save: () => response(400, { detail: { errors: ["Official answer A1 has wrong length"] } }),
    });
    await screen.findByRole("application", { name: "Crossword grid" });
    fireEvent.click(screen.getByRole("button", { name: /Save Puzzle/i }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Official answer A1 has wrong length");
  });

  it("edge: saving while offline catches the error and shows a generic failure message", async () => {
    await loadFixture({
      parse: () => response(200, { puzzle: puzzleFixture, validation_errors: [] }),
      save: () => Promise.reject(new TypeError("Failed to fetch")),
    });
    await screen.findByRole("application", { name: "Crossword grid" });
    fireEvent.click(screen.getByRole("button", { name: /Save Puzzle/i }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/Network error/i);
    expect(screen.getByRole("button", { name: /Save Puzzle/i })).toBeTruthy();
  });
});

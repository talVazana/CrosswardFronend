import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor, act } from "@testing-library/react";

const harness = vi.hoisted(() => ({
  options: null as null | {
    onEvent?: (event: MessageEvent) => void;
    onStateFetched?: (state: unknown) => void;
  },
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ roomId: "room-1" }),
}));

vi.mock("../src/hooks/useRoomLiveUpdates", () => ({
  useRoomLiveUpdates: (options: typeof harness.options) => {
    harness.options = options;
    return { connectionState: "connected" };
  },
}));

import RoomLobbyPage from "../src/app/rooms/[roomId]/page";

const ROOM_ID = "room-1";

const puzzle = {
  puzzleId: "live-puzzle",
  title: "Live",
  width: 5,
  height: 1,
  cells: Array.from({ length: 5 }, (_, col) => ({
    row: 0,
    col,
    type: "white",
    number: col === 4 ? 1 : null,
    startsAcross: col === 4,
    startsDown: false,
  })),
  clues: [
    {
      clueId: "A1",
      number: 1,
      direction: "across" as const,
      text: "",
      answerLength: 5,
    },
  ],
};

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as unknown as Response;
}

function makeEvent(type: string, payload: unknown): MessageEvent {
  return {
    type,
    data: typeof payload === "string" ? payload : JSON.stringify(payload),
  } as MessageEvent;
}

function emit(type: string, payload: unknown) {
  act(() => {
    harness.options?.onEvent?.(makeEvent(type, payload));
  });
}

function DummyBoard() {
  return <RoomLobbyPage />;
}

async function renderBoard() {
  render(<DummyBoard />);
  await screen.findByText("Test Room");
}

function cellShadow(testId: string): string {
  return (screen.getByTestId(testId) as HTMLElement).style.boxShadow;
}

function cellText(testId: string): string {
  return screen.getByTestId(testId).textContent ?? "";
}

function typeOnGrid(text: string) {
  const grid = screen.getByRole("application", { name: "Crossword grid" });
  for (const char of text) {
    fireEvent.keyDown(grid, { key: char });
  }
}

async function selectAndType() {
  fireEvent.click(screen.getByTestId("cell-0-4"));
  typeOnGrid("HELLO");
  expect(cellText("cell-0-4")).toContain("H");
  expect(cellText("cell-0-0")).toContain("O");
}

beforeEach(() => {
  harness.options = null;
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      jsonResponse({
        roomId: ROOM_ID,
        title: "Test Room",
        status: "active",
        puzzle,
        solvedClues: [],
        players: [],
      }),
    ),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("TASK-040 frontend live event idempotency", () => {
  it("Given an active board with clue A1 unsolved, when CLUE_SOLVED with clueId A1 firstSolverColor #FF0000 arrives, then A1 is marked solved and the color is applied", async () => {
    await renderBoard();
    expect(cellShadow("cell-0-0")).toBe("");

    emit("CLUE_SOLVED", {
      clueId: "A1",
      firstSolverColor: "#FF0000",
      points: 10,
    });

    await waitFor(() => {
      expect(cellShadow("cell-0-0")).toMatch(/rgba\(255,\s*0,\s*0/i);
    });
    expect(cellShadow("cell-0-1")).toMatch(/rgba\(255,\s*0,\s*0/i);
    expect(cellShadow("cell-0-2")).toMatch(/rgba\(255,\s*0,\s*0/i);
    expect(
      (screen.getByTestId("cell-0-0") as HTMLElement).style.backgroundColor,
    ).toMatch(/rgba\(255,\s*0,\s*0/i);
  });

  it("Given the board where A1 is already solved, when the exact same CLUE_SOLVED event arrives again, then the state remains completely unchanged with no errors or duplicates", async () => {
    await renderBoard();
    const event = {
      clueId: "A1",
      firstSolverColor: "#FF0000",
      points: 10,
    };

    emit("CLUE_SOLVED", event);
    await waitFor(() => {
      expect(cellShadow("cell-0-0")).toMatch(/rgba\(255,\s*0,\s*0/i);
    });

    const before = {
      c00: cellShadow("cell-0-0"),
      c01: cellShadow("cell-0-1"),
      c02: cellShadow("cell-0-2"),
    };

    emit("CLUE_SOLVED", event);
    emit("CLUE_SOLVED", event);

    expect(cellShadow("cell-0-0")).toBe(before.c00);
    expect(cellShadow("cell-0-1")).toBe(before.c01);
    expect(cellShadow("cell-0-2")).toBe(before.c02);
    expect(screen.getByRole("application", { name: "Crossword grid" })).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("Given the player typed HELLO into the grid for A1, when ROOM_STATUS_CHANGED sets the room to paused, then the letters remain intact and Submit is disabled", async () => {
    await renderBoard();
    await selectAndType();

    emit("ROOM_STATUS_CHANGED", { status: "paused" });

    await waitFor(() => {
      expect(cellText("cell-0-4")).toContain("H");
    });
    expect(cellText("cell-0-0")).toContain("O");
    expect(
      (screen.getByRole("button", { name: "Submit" }) as HTMLButtonElement).disabled,
    ).toBe(true);
  });

  it("Edge: an unknown event type arriving through the stream is gracefully ignored without throwing exceptions", async () => {
    await renderBoard();

    expect(() => {
      emit("SOMETHING_UNKNOWN", { foo: "bar" });
      emit("SOMETHING_UNKNOWN", "this is not json");
    }).not.toThrow();

    expect(screen.getByRole("application", { name: "Crossword grid" })).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("Acceptance: public CLUE_SOLVED events never touch the player's local unsubmitted letters", async () => {
    await renderBoard();
    await selectAndType();

    emit("CLUE_SOLVED", {
      clueId: "A1",
      firstSolverColor: "#00FF00",
      points: 25,
    });

    await waitFor(() => {
      expect(cellShadow("cell-0-0")).toMatch(/rgba\(0,\s*255,\s*0/i);
    });
    expect(
      (screen.getByTestId("cell-0-1") as HTMLElement).style.backgroundColor,
    ).toMatch(/rgba\(0,\s*255,\s*0/i);
    expect(cellText("cell-0-4")).toContain("H");
    expect(cellText("cell-0-0")).toContain("O");
  });

  it("Acceptance: out-of-order events (status change before clue solved, malformed and duplicate payloads) do not crash the board", async () => {
    await renderBoard();

    emit("ROOM_STATUS_CHANGED", { status: "paused" });
    emit("CLUE_SOLVED", { clueId: "A1" });
    emit("CLUE_SOLVED", {
      clueId: "A1",
      firstSolverColor: "#FF0000",
      points: 10,
    });
    emit("ROOM_STATUS_CHANGED", { status: "active" });
    emit("CLUE_SOLVED", {
      clueId: "A1",
      firstSolverColor: "#FF0000",
      points: 10,
    });
    emit("ROOM_STATUS_CHANGED", "garbage");

    expect(screen.getByRole("application", { name: "Crossword grid" })).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
    await waitFor(() => {
      expect(cellShadow("cell-0-0")).toMatch(/rgba\(255,\s*0,\s*0/i);
    });
  });
});

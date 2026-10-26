import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor, act } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  useParams: () => ({ roomId: "room-1" }),
}));

const harness = vi.hoisted(() => ({
  onNext: null as null | ((room: unknown) => void),
  onError: null as null | ((error: Error) => void),
}));

vi.mock("../src/lib/roomsStore", () => ({
  subscribeRoom: (
    _roomId: string,
    onNext: (room: unknown) => void,
    onError?: (error: Error) => void,
  ) => {
    harness.onNext = onNext;
    harness.onError = onError ?? null;
    return () => {};
  },
  subscribeRooms: () => () => {},
}));

import RoomLobbyPage from "../src/app/rooms/[roomId]/page";

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

function baseRoom() {
  return {
    roomId: "room-1",
    title: "Test Room",
    status: "active",
    players: [],
    solvedClues: [],
    puzzle,
  };
}

function emit(room: unknown) {
  act(() => {
    harness.onNext?.(room);
  });
}

async function renderBoard() {
  render(<RoomLobbyPage />);
  emit(baseRoom());
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
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).endsWith("/player-progress")) {
        return jsonResponse({ solved: [], revealed: [] });
      }
      throw new Error(`Unexpected fetch: ${String(input)}`);
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  harness.onNext = null;
  harness.onError = null;
});

describe("Firestore room state updates", () => {
  it("marks clue A1 solved and applies its color when solvedClues updates", async () => {
    await renderBoard();
    expect(cellShadow("cell-0-0")).toBe("");

    emit({
      ...baseRoom(),
      solvedClues: [{ clueId: "A1", firstSolverColor: "#FF0000" }],
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

  it("applies an identical duplicate snapshot without changing state or raising errors", async () => {
    await renderBoard();
    const solved = {
      ...baseRoom(),
      solvedClues: [{ clueId: "A1", firstSolverColor: "#FF0000" }],
    };

    emit(solved);
    await waitFor(() => {
      expect(cellShadow("cell-0-0")).toMatch(/rgba\(255,\s*0,\s*0/i);
    });

    const before = {
      c00: cellShadow("cell-0-0"),
      c01: cellShadow("cell-0-1"),
      c02: cellShadow("cell-0-2"),
    };

    emit(solved);
    emit(solved);

    expect(cellShadow("cell-0-0")).toBe(before.c00);
    expect(cellShadow("cell-0-1")).toBe(before.c01);
    expect(cellShadow("cell-0-2")).toBe(before.c02);
    expect(screen.getByRole("application", { name: "Crossword grid" })).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("keeps typed letters and disables Submit when the room pauses", async () => {
    await renderBoard();
    await selectAndType();

    emit({ ...baseRoom(), status: "paused" });

    await waitFor(() => {
      expect(cellText("cell-0-4")).toContain("H");
    });
    expect(cellText("cell-0-0")).toContain("O");
    expect(
      (screen.getByRole("button", { name: "Submit" }) as HTMLButtonElement).disabled,
    ).toBe(true);
  });

  it("never touches local unsubmitted letters when solvedClues updates", async () => {
    await renderBoard();
    await selectAndType();

    emit({
      ...baseRoom(),
      solvedClues: [{ clueId: "A1", firstSolverColor: "#00FF00" }],
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
});

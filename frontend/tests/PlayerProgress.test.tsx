import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render, screen } from "@testing-library/react";

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
import ClueList from "../src/components/ClueList";

const clues = [
  {
    clueId: "A1",
    number: 1,
    direction: "across" as const,
    text: "Feline pet",
    answerLength: 3,
  },
  {
    clueId: "D1",
    number: 1,
    direction: "down" as const,
    text: "Opposite of off",
    answerLength: 2,
  },
  {
    clueId: "A2",
    number: 2,
    direction: "across" as const,
    text: "A pronoun",
    answerLength: 1,
  },
];

function jsonResponse(data: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => data,
  } as unknown as Response;
}

const room = {
  roomId: "room-1",
  title: "Progress Room",
  status: "active",
  players: [],
  solvedClues: [],
  puzzle: {
    puzzleId: "puzzle-1",
    title: "Progress",
    width: 1,
    height: 2,
    cells: [
      { row: 0, col: 0, type: "white", number: 1, startsAcross: true, startsDown: true },
      { row: 1, col: 0, type: "white", number: 2, startsAcross: true, startsDown: false },
    ],
    clues,
  },
};

function emitRoom(value: unknown) {
  act(() => {
    harness.onNext?.(value);
  });
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  harness.onNext = null;
  harness.onError = null;
});

describe("player clue progress", () => {
  it("checks and grays clues solved or revealed by the current player", () => {
    render(
      <ClueList
        clues={clues}
        playerSolvedClueIds={new Set(["A1"])}
        playerRevealedClueIds={new Set(["D1"])}
      />,
    );

    const solved = screen.getByRole("checkbox", {
      name: "Clue 1 Across completed",
    }) as HTMLInputElement;
    const revealed = screen.getByRole("checkbox", {
      name: "Clue 1 Down completed",
    }) as HTMLInputElement;
    const untouched = screen.getByRole("checkbox", {
      name: "Clue 2 Across not completed",
    }) as HTMLInputElement;

    expect(solved.checked).toBe(true);
    expect(solved.disabled).toBe(true);
    expect(revealed.checked).toBe(true);
    expect(untouched.checked).toBe(false);
    expect(screen.getByText("Feline pet").closest("li")?.className).toContain(
      "text-blue-900/40",
    );
    expect(
      screen.getByText("Opposite of off").closest("li")?.className,
    ).toContain("text-blue-900/40");
    expect(screen.getByText("A pronoun").closest("li")?.className).not.toContain(
      "text-blue-900/40",
    );
  });

  it("loads the current player's progress when the room opens", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/rooms/room-1/player-progress")) {
          return jsonResponse({ solved: ["A1"], revealed: ["D1"] });
        }
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    render(<RoomLobbyPage />);
    emitRoom(room);
    await screen.findByText("Progress Room");

    const solved = (await screen.findByRole("checkbox", {
      name: "Clue 1 Across completed",
    })) as HTMLInputElement;
    const revealed = screen.getByRole("checkbox", {
      name: "Clue 1 Down completed",
    }) as HTMLInputElement;

    expect(solved.checked).toBe(true);
    expect(revealed.checked).toBe(true);
  });
});

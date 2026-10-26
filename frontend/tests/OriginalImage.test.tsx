import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";

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

function jsonResponse(data: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => data,
  } as unknown as Response;
}

const room = {
  roomId: "room-1",
  title: "Image Test Room",
  status: "active",
  players: [],
  solvedClues: [],
  puzzle: {
    puzzleId: "puzzle-1",
    title: "Test",
    width: 1,
    height: 1,
    cells: [
      {
        row: 0,
        col: 0,
        type: "white",
        number: 1,
        startsAcross: true,
        startsDown: false,
      },
    ],
    clues: [
      {
        clueId: "A1",
        number: 1,
        direction: "across",
        text: "Test clue",
        answerLength: 1,
      },
    ],
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

describe("original puzzle image", () => {
  it("opens and closes the source image from the player room", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/rooms/room-1/player-progress")) {
          return jsonResponse({ solved: [], revealed: [] });
        }
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    render(<RoomLobbyPage />);
    emitRoom(room);
    await screen.findByText("Image Test Room");

    fireEvent.click(
      screen.getByRole("button", { name: "Show original image" }),
    );

    expect(
      screen.getByRole("dialog", { name: "Original puzzle image" }),
    ).toBeTruthy();
    const image = screen.getByAltText(
      "Original published crossword page for this room",
    ) as HTMLImageElement;
    expect(image.getAttribute("src")).toBe("/puzzle-source.jpg");

    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(
      screen.queryByRole("dialog", { name: "Original puzzle image" }),
    ).toBeNull();
  });

  it("closes the image on Escape", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/rooms/room-1/player-progress")) {
          return jsonResponse({ solved: [], revealed: [] });
        }
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    render(<RoomLobbyPage />);
    emitRoom(room);
    await screen.findByText("Image Test Room");

    fireEvent.click(
      screen.getByRole("button", { name: "Show original image" }),
    );
    expect(
      screen.getByRole("dialog", { name: "Original puzzle image" }),
    ).toBeTruthy();

    fireEvent.keyDown(window, { key: "Escape" });
    expect(
      screen.queryByRole("dialog", { name: "Original puzzle image" }),
    ).toBeNull();
  });
});

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  useParams: () => ({ roomId: "room-1" }),
}));

vi.mock("../src/hooks/useRoomLiveUpdates", () => ({
  useRoomLiveUpdates: () => ({ connectionState: "connected" }),
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

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("original puzzle image", () => {
  it("opens and closes the source image from the player room", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/rooms/room-1/state")) return jsonResponse(room);
        if (url.endsWith("/rooms/room-1/scores")) return jsonResponse([]);
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    render(<RoomLobbyPage />);
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
        if (url.endsWith("/rooms/room-1/state")) return jsonResponse(room);
        if (url.endsWith("/rooms/room-1/scores")) return jsonResponse([]);
        throw new Error(`Unexpected fetch: ${url}`);
      }),
    );

    render(<RoomLobbyPage />);
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
